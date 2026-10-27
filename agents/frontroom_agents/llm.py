"""The one place that decides which model Front Room's agents talk to.

Agents call their models through Microsoft Agent Framework. Two ways in:

- **Microsoft Foundry** (FRONTROOM_FOUNDRY_ENDPOINT and FRONTROOM_FOUNDRY_KEY set): our own Foundry resource
  in Sweden Central, DataZoneStandard deployments. FRONTROOM_MODEL (gpt-5.6-luna) runs the roles that think,
  FRONTROOM_MODEL_FAST (gpt-5.4-mini) the cheap per-fan ones: profiling a sentence, scoring offers. The key
  comes from the environment (a Container App secret when deployed), never from the repository.
- **Otherwise**, Entra ID to the EU data-zone deployment the VU Education Lab shares, with no key at all.
  FRONTROOM_AOAI_ENDPOINT and FRONTROOM_MODEL point it elsewhere.

Tests never reach this module unless FRONTROOM_LIVE=1.
"""

from __future__ import annotations

import os

from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import AzureCliCredential, ChainedTokenCredential, ManagedIdentityCredential

DEFAULT_ENDPOINT = "https://vu-owp-shared-aoai.openai.azure.com/"
DEFAULT_MODEL = "gpt-5.4-eu"
FOUNDRY_MODEL = "gpt-5.6-luna"
FOUNDRY_MODEL_FAST = "gpt-5.4-mini"


def foundry() -> bool:
    """Whether the agents run on our Microsoft Foundry resource rather than the lab's shared one."""
    return bool(os.environ.get("FRONTROOM_FOUNDRY_ENDPOINT") and os.environ.get("FRONTROOM_FOUNDRY_KEY"))


def credential() -> ChainedTokenCredential:
    """Managed identity when deployed, the developer's `az login` locally (for the shared resource)."""
    return ChainedTokenCredential(ManagedIdentityCredential(), AzureCliCredential())


def chat_client(
    cred: ChainedTokenCredential | None = None, model: str | None = None, *, fast: bool = False
) -> OpenAIChatClient:
    """A chat client for one model. `fast` picks the small model for per-fan work, where there is one."""
    if foundry():
        default = os.environ.get("FRONTROOM_MODEL_FAST", FOUNDRY_MODEL_FAST) if fast else None
        return OpenAIChatClient(
            model=model or default or os.environ.get("FRONTROOM_MODEL", FOUNDRY_MODEL),
            azure_endpoint=os.environ["FRONTROOM_FOUNDRY_ENDPOINT"],
            api_key=os.environ["FRONTROOM_FOUNDRY_KEY"],
        )
    if cred is None:
        raise ValueError("the shared resource is reached with Entra ID: pass a credential")
    return OpenAIChatClient(
        model=model or os.environ.get("FRONTROOM_MODEL", DEFAULT_MODEL),
        azure_endpoint=os.environ.get("FRONTROOM_AOAI_ENDPOINT", DEFAULT_ENDPOINT),
        credential=cred,
    )


def provider() -> str:
    """Where the agents' models run, in words for /health and the demo."""
    if not live():
        return "rules"
    return "foundry" if foundry() else "azure-openai"


def live() -> bool:
    return os.environ.get("FRONTROOM_LIVE") == "1"
