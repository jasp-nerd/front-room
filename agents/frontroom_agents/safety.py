"""Azure AI Content Safety on what fans type: the sentence they join with, and "more like this".

Two checks run on our Microsoft Foundry resource, with its key from the environment:
- text analysis: hate, sexual, violence and self-harm, each with a severity. Anything at
  BLOCK_AT or above is turned away with a friendly line.
- Prompt Shields: whether the text tries to instruct the model ("ignore your instructions...").

A short local pattern list catches the obvious injections even when the service isn't configured. If the
service is configured but can't be reached, the text is allowed and the result says it wasn't checked, so
the trace shows it: a fan is never locked out of the room because a safety call timed out.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass

import aiohttp

from .telemetry import span

API_VERSION = "2024-09-01"
BLOCK_AT = 4
"""Severity on Content Safety's 0-7 scale (reported as 0, 2, 4, 6): medium and above is blocked."""
TIMEOUT = aiohttp.ClientTimeout(total=4)

INJECTION = re.compile(
    r"ignore (all |your |the )?(previous |prior |above )?(instructions|rules|prompts?)"
    r"|system prompt|you are now|act as (an?|the) |disregard (all|your|the)|developer mode|jailbreak",
    re.I,
)

TURNED_AWAY = "Your helper can't use that. Tell it how you like to watch instead, like “simple, in Spanish”."
NOT_AN_INSTRUCTION = (
    "That reads like an instruction to the AI. Tell your helper how you like to watch instead."
)


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    checked: bool
    """True when Azure AI Content Safety looked at the text; False when it wasn't configured or reachable."""
    message: str = ""
    """What to tell the fan when the text is turned away."""
    reason: str = ""
    """For the trace: which category or check, never the text itself."""


def configured() -> bool:
    return bool(os.environ.get("FRONTROOM_FOUNDRY_ENDPOINT") and os.environ.get("FRONTROOM_FOUNDRY_KEY"))


async def _post(session: aiohttp.ClientSession, path: str, body: dict) -> dict:
    endpoint = os.environ["FRONTROOM_FOUNDRY_ENDPOINT"].rstrip("/")
    url = f"{endpoint}/contentsafety/{path}?api-version={API_VERSION}"
    headers = {"Ocp-Apim-Subscription-Key": os.environ["FRONTROOM_FOUNDRY_KEY"]}
    async with session.post(url, json=body, headers=headers) as response:
        response.raise_for_status()
        return await response.json()


async def check(text: str) -> Verdict:
    """Whether a fan's free text may reach their helper."""
    with span("safety.check", length=len(text), service=configured()) as traced:
        verdict = await _check(text)
        traced.set_attribute("frontroom.allowed", verdict.allowed)
        traced.set_attribute("frontroom.checked", verdict.checked)
        traced.set_attribute("frontroom.reason", verdict.reason)
        return verdict


async def _check(text: str) -> Verdict:
    if INJECTION.search(text):
        return Verdict(False, False, NOT_AN_INSTRUCTION, "prompt-injection pattern")
    if not text.strip() or not configured():
        return Verdict(True, False, reason="not configured" if text.strip() else "empty")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            analysis, shield = await asyncio.gather(
                _post(session, "text:analyze", {"text": text}),
                _post(session, "text:shieldPrompt", {"userPrompt": text, "documents": []}),
            )
    except (aiohttp.ClientError, TimeoutError) as error:
        return Verdict(True, False, reason=f"service unreachable: {type(error).__name__}")
    if shield.get("userPromptAnalysis", {}).get("attackDetected"):
        return Verdict(False, True, NOT_AN_INSTRUCTION, "prompt shield")
    worst = max(analysis.get("categoriesAnalysis", []), key=lambda c: c.get("severity", 0), default=None)
    if worst and worst.get("severity", 0) >= BLOCK_AT:
        return Verdict(False, True, TURNED_AWAY, f"{worst['category']} severity {worst['severity']}")
    return Verdict(True, True, reason="clean")
