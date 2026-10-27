"""Turns what a fan types when they join into their private profile.

The raw text is used once and dropped: only the profile is kept, on the fan's side. A kid's text is never
stored or logged, even in traces.
"""

from __future__ import annotations

from typing import Protocol

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from . import squad
from .profile import FanProfile, Metric, profile_instructions

# Words that name each number, in English and Spanish.
METRIC_WORDS: dict[Metric, tuple[str, ...]] = {
    "distance": ("distance", "how far", "kilometre", "km", "distancia"),
    "top-speed": ("top speed", "fastest", "speed", "sprint", "velocidad", "rápido"),
    "shots-on-target": ("shots on target", "shots", "tiros", "disparos"),
    "pass-accuracy": ("pass accuracy", "passing", "passes", "pases"),
    "possession": ("possession", "posesión"),
}


def followed(text: str, names: list[str]) -> list[str]:
    """The squad names a fan mentioned, whole words only, in the order they appear in the squad."""
    words = set(text.replace(",", " ").replace(".", " ").replace("!", " ").split())
    return [n for n in names if n.lower() in text and (" " in n or n.lower() in words)]


def metric_in(text: str) -> Metric | None:
    for metric, words in METRIC_WORDS.items():
        if any(w in text for w in words):
            return metric
    return None


class Profiler(Protocol):
    async def profile(self, told: str) -> FanProfile: ...


class RuleProfiler:
    """Keyword matching in English and Spanish. The fallback, and what tests use."""

    async def profile(self, told: str) -> FanProfile:
        text = told.lower()
        club = "ashvale" if "ashvale" in text else "kestrel" if "kestrel" in text else None
        spanish = any(w in text for w in ("español", "spanish", "solo lo", "por favor"))
        if any(w in text for w in ("i'm 10", "i am 10", "years old", "kid")):
            depth = "kid"
        elif any(w in text for w in ("big text", "talk me through", "can't see", "listen")):
            depth = "audio"
        elif any(w in text for w in ("numbers", "shape", "tactic", "stats", "data")):
            depth = "analyst"
        else:
            depth = "casual"
        needs = [
            n
            for n, words in {
                "captions": ("caption", "subtítulo"),
                "described-audio": ("talk me through", "describe"),
                "large-text": ("big text", "large text"),
            }.items()
            if any(w in text for w in words)
        ]
        return FanProfile(
            club=club,
            depth=depth,
            language="es" if spanish else "en",
            needs=needs,
            players=followed(text, squad.labels()),
            metric=metric_in(text),
        )


class ModelProfiler:
    def __init__(self, client: OpenAIChatClient, fallback: Profiler | None = None):
        self._agent = Agent(client=client, name="profiler", instructions=profile_instructions(squad.labels()))
        self._fallback = fallback or RuleProfiler()

    async def profile(self, told: str) -> FanProfile:
        try:
            response = await self._agent.run(told, options={"response_format": FanProfile})
            if response.value is None:
                raise ValueError("the profiler returned no profile")
            return await self.grounded(told, response.value)
        except Exception:
            return await self._fallback.profile(told)

    async def grounded(self, told: str, profile: FanProfile) -> FanProfile:
        """Keep only players who are really in tonight's squads, and only access needs the fan's own words
        support: an instruction hidden in the text must not switch every need on."""
        known = set(squad.labels())
        heard = set((await self._fallback.profile(told)).needs)
        return profile.model_copy(
            update={
                "players": [p for p in profile.players if p in known],
                "needs": [n for n in profile.needs if n in heard],
            }
        )
