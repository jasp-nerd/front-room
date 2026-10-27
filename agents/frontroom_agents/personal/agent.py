"""A personal agent speaks for one fan in the room.

It holds the fan's private profile, values each overlay the room could put on the shared TV, and places bids.
How it values them is pluggable: a model-backed scorer for real rooms, and a plain rule-based scorer for tests
and for when the model is unreachable, so a room never stalls because one call failed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import ClassVar, Literal, Protocol

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from pydantic import BaseModel, Field

from ..room.director import Bid, Candidate
from .profile import ClubId, FanProfile

OfferKind = Literal["tactics", "story", "keeper", "described", "player"]


@dataclass(frozen=True)
class Offer:
    """An overlay the room could put on the TV, as every agent sees it. It carries no fan data."""

    candidate: Candidate
    title: str
    summary: str
    kind: OfferKind
    favours: ClubId | None = None
    player: str | None = None
    """For a player card: the player it is about, as fans name them (personal/squad.py)."""


@dataclass(frozen=True)
class Valuation:
    utility: float
    reason: str


class Scorer(Protocol):
    async def value(self, profile: FanProfile, offers: list[Offer]) -> dict[str, Valuation]: ...


class RuleScorer:
    """Plain preferences by depth and club. Predictable, instant, and the fallback for every agent."""

    BY_DEPTH: ClassVar[dict[str, dict[OfferKind, float]]] = {
        "analyst": {"tactics": 0.9, "story": 0.4, "keeper": 0.5, "described": 0.1, "player": 0.4},
        "casual": {"tactics": 0.3, "story": 0.7, "keeper": 0.6, "described": 0.2, "player": 0.3},
        "kid": {"tactics": 0.2, "story": 0.8, "keeper": 0.5, "described": 0.2, "player": 0.5},
        "audio": {"tactics": 0.3, "story": 0.5, "keeper": 0.3, "described": 0.9, "player": 0.2},
    }
    FOLLOWED = 0.95
    """A card about a player the fan follows is the thing they most want to see."""

    async def value(self, profile: FanProfile, offers: list[Offer]) -> dict[str, Valuation]:
        values = {}
        for offer in offers:
            if offer.player and offer.player in profile.players:
                values[offer.candidate.id] = Valuation(self.FOLLOWED, "rule: a player they follow")
                continue
            utility = self.BY_DEPTH[profile.depth][offer.kind]
            if offer.favours and profile.club:
                utility += 0.1 if offer.favours == profile.club else -0.3
            values[offer.candidate.id] = Valuation(round(min(max(utility, 0.0), 1.0), 2), "rule")
        return values


class _Rated(BaseModel):
    candidate_id: str
    utility: float = Field(ge=0, le=1, description="How much the fan wants this on the shared TV now.")
    reason: str = Field(description="One short sentence, for the fan's own phone only.")


class _Ratings(BaseModel):
    ratings: list[_Rated]


BID_INSTRUCTIONS = """\
You are one football fan's personal agent in a living room where several fans share one TV.
You know this fan's private profile. For each overlay the room could show on the shared TV, rate from 0 to 1
how much this fan would want it there right now. Anything that doesn't win the TV still reaches the fan's own
phone, so rate only the shared screen. Never invent overlays and never mention other fans.
"""


class ModelScorer:
    """Values offers with a model through Agent Framework, falling back to rules if the call fails."""

    def __init__(self, client: OpenAIChatClient, fallback: Scorer | None = None):
        self._agent = Agent(client=client, name="personal-agent", instructions=BID_INSTRUCTIONS)
        self._fallback = fallback or RuleScorer()

    async def value(self, profile: FanProfile, offers: list[Offer]) -> dict[str, Valuation]:
        prompt = json.dumps(
            {
                "profile": profile.model_dump(),
                "overlays": [
                    {
                        "id": o.candidate.id,
                        "title": o.title,
                        "summary": o.summary,
                        "favours": o.favours,
                        "player": o.player,
                    }
                    for o in offers
                ],
            }
        )
        try:
            response = await self._agent.run(prompt, options={"response_format": _Ratings})
            if response.value is None:
                raise ValueError("the scorer returned no ratings")
            rated = response.value.ratings
        except Exception:
            return await self._fallback.value(profile, offers)
        known = {o.candidate.id for o in offers}
        return {r.candidate_id: Valuation(r.utility, r.reason) for r in rated if r.candidate_id in known}


@dataclass
class PersonalAgent:
    agent_id: str
    profile: FanProfile
    scorer: Scorer
    reasons: dict[str, str] = field(default_factory=dict)
    """Why the agent bid what it did. Shown on the fan's own phone, never sent to the room."""

    async def bid(self, offers: list[Offer]) -> list[Bid]:
        values = await self.scorer.value(self.profile, offers)
        self.reasons = {cid: v.reason for cid, v in values.items()}
        return [Bid(self.agent_id, cid, v.utility) for cid, v in values.items() if v.utility > 0]
