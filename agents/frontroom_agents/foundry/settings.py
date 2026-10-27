"""Where Front Room's Foundry project is, and how to reach its models.

    FRONTROOM_FOUNDRY_ENDPOINT   https://vu-front-room-foundry.cognitiveservices.azure.com/
    FRONTROOM_FOUNDRY_PROJECT    https://vu-front-room-foundry.services.ai.azure.com/api/projects/front-room
    FRONTROOM_FOUNDRY_KEY        the resource key (a Container App secret when deployed; never in the repo)
    FRONTROOM_MODEL              gpt-5.6-luna, the reasoning agents' deployment
    FRONTROOM_MODEL_FAST         gpt-5.4-mini
    FRONTROOM_JUDGE_MODEL        gpt-5.4, the evaluations' judge: a different model from the agents it grades

Model calls, Content Safety and Speech all use the resource key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from agent_framework.openai import OpenAIChatClient

API_VERSION = "2024-10-21"
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


@dataclass(frozen=True)
class Settings:
    endpoint: str
    project: str
    key: str
    model: str
    model_fast: str
    judge: str


def _from_env_file() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    pairs = (line.split("=", 1) for line in ENV_FILE.read_text().splitlines() if "=" in line)
    return {k.strip(): v.strip() for k, v in pairs if not k.lstrip().startswith("#")}


def settings() -> Settings:
    found = _from_env_file() | dict(os.environ)
    missing = [k for k in ("FRONTROOM_FOUNDRY_ENDPOINT", "FRONTROOM_FOUNDRY_KEY") if not found.get(k)]
    if missing:
        raise RuntimeError(f"Foundry settings missing: {', '.join(missing)} (see .env.example)")
    return Settings(
        endpoint=found["FRONTROOM_FOUNDRY_ENDPOINT"],
        project=found.get("FRONTROOM_FOUNDRY_PROJECT", ""),
        key=found["FRONTROOM_FOUNDRY_KEY"],
        model=found.get("FRONTROOM_MODEL", "gpt-5.6-luna"),
        model_fast=found.get("FRONTROOM_MODEL_FAST", "gpt-5.4-mini"),
        judge=found.get("FRONTROOM_JUDGE_MODEL", "gpt-5.4"),
    )


def chat_client(model: str | None = None) -> OpenAIChatClient:
    """An Agent Framework client on one of the Foundry project's deployments."""
    s = settings()
    return OpenAIChatClient(model=model or s.model, azure_endpoint=s.endpoint, api_key=s.key)


def judge_config() -> dict[str, str]:
    """The model configuration azure-ai-evaluation's AI-assisted evaluators judge with."""
    s = settings()
    return {
        "azure_endpoint": s.endpoint,
        "azure_deployment": s.judge,
        "api_key": s.key,
        "api_version": API_VERSION,
    }
