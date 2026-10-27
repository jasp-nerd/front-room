"""One decision round in a room: ask every personal agent for bids, wait no longer than the deadline, decide.

An agent that is late or fails is dropped from this round only. The room still decides on time, the ledger
names who was dropped, and that fan keeps their waiting time for the next round.

The decision itself is made by a Director: the local one by default, or one reached over A2A
(frontroom_agents.a2a.remote.RemoteDirector) when the broadcaster runs it somewhere else.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from ..personal.agent import Offer, PersonalAgent
from .director import Bid, Candidate, Decision, RoomState, decide

# Long enough for every agent's model call in a normal round, short enough that the TV never waits on one.
BID_DEADLINE_S = 4.0


class Director(Protocol):
    async def decide(self, candidates: list[Candidate], bids: list[Bid], state: RoomState) -> Decision: ...


class LocalDirector:
    """The Director in this process: a plain function call."""

    async def decide(self, candidates: list[Candidate], bids: list[Bid], state: RoomState) -> Decision:
        return decide(candidates, bids, state)


class FallbackDirector:
    """Ask a Director somewhere else (over A2A); if it doesn't answer in time, decide here by the same rules.

    The rules are deterministic, so the room gets the same answer either way, and never waits on the network.
    `used` says which one decided the last round: "a2a" or "local-fallback".
    """

    def __init__(self, remote: Director, timeout_s: float = 2.0) -> None:
        self.remote = remote
        self.timeout_s = timeout_s
        self.used = "a2a"

    async def decide(self, candidates: list[Candidate], bids: list[Bid], state: RoomState) -> Decision:
        try:
            decision = await asyncio.wait_for(self.remote.decide(candidates, bids, state), self.timeout_s)
            self.used = "a2a"
            return decision
        except Exception:  # any failure to reach the remote Director falls back to the same rules
            self.used = "local-fallback"
            return decide(candidates, bids, state)


@dataclass(frozen=True)
class Round:
    decision: Decision
    bids: list[Bid]
    dropped: list[str]


async def run_round(
    agents: list[PersonalAgent],
    offers: list[Offer],
    state: RoomState,
    deadline_s: float = BID_DEADLINE_S,
    director: Director | None = None,
) -> Round:
    tasks = {agent.agent_id: asyncio.create_task(agent.bid(offers)) for agent in agents}
    await asyncio.wait(tasks.values(), timeout=deadline_s)

    bids: list[Bid] = []
    dropped: list[str] = []
    for agent_id, task in tasks.items():
        if task.done() and task.exception() is None:
            bids.extend(task.result())
        else:
            task.cancel()
            dropped.append(agent_id)

    decision = await (director or LocalDirector()).decide([offer.candidate for offer in offers], bids, state)
    return Round(decision=decision, bids=bids, dropped=dropped)
