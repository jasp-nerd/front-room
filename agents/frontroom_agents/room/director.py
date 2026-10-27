"""The Room Director: decides what the shared TV shows when the fans in a room want different things.

It allocates, it does not write. Personal agents send bids (a utility per candidate overlay); the Director
removes candidates that break a house rule, weights each fan by how long they have gone without seeing
their choice on the TV, and picks the overlay with the highest weighted support. Everything it did and
why is returned as a ledger entry, which is what the room's "Why this?" screen shows.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from time import perf_counter

# A fan who has gone this long without their choice on the TV counts half as much again as everyone else.
FAIRNESS_HORIZON_S = 720.0
FAIRNESS_MAX_BONUS = 0.5

# The TV returns to the plain match for at least this long between overlays.
MIN_GAP_MS = 20_000

# Each agent's bids in a round add up to at most this. An agent that "wants everything" spreads its budget
# thin instead of outvoting the room, so a profile that says "always bid max for me" gains nothing.
BID_BUDGET = 1.0


class Constraint(StrEnum):
    NEUTRAL_FRAMING = "neutral-framing"
    ONE_OVERLAY = "one-overlay"
    MIN_GAP = "min-gap"
    VAR_HOLD = "var-hold"
    SPOILER_GATE = "spoiler-gate"


@dataclass(frozen=True)
class Candidate:
    """An overlay that could go on the shared TV. `partisan` means it favours one club."""

    id: str
    pts: int
    partisan: bool


@dataclass(frozen=True)
class Bid:
    agent_id: str
    candidate_id: str
    utility: float


@dataclass
class RoomState:
    """What the Director knows about the room. It never sees fan profiles, only these facts."""

    agent_ids: list[str]
    both_clubs_present: bool
    tv_pts: int
    overlay_on_air: bool = False
    last_overlay_end_pts: int | None = None
    var_check: bool = False
    seconds_without_screen: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Weight:
    agent_id: str
    weight: float
    seconds_without_screen: float


@dataclass(frozen=True)
class Scored:
    candidate_id: str
    raw_score: float
    fair_score: float
    struck_by: Constraint | None
    won: bool
    asked_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    pts: int
    weights: list[Weight]
    candidates: list[Scored]
    winner: str | None
    delivered_privately: dict[str, str]
    decided_in_ms: float


def fairness_weight(seconds_without_screen: float) -> float:
    waited = min(max(seconds_without_screen, 0.0), FAIRNESS_HORIZON_S)
    return 1.0 + FAIRNESS_MAX_BONUS * waited / FAIRNESS_HORIZON_S


def strike(candidate: Candidate, state: RoomState) -> Constraint | None:
    """The first house rule this candidate breaks, if any. Order matters only for what the ledger names."""
    if candidate.pts > state.tv_pts:
        return Constraint.SPOILER_GATE
    if state.var_check:
        return Constraint.VAR_HOLD
    if state.overlay_on_air:
        return Constraint.ONE_OVERLAY
    if state.last_overlay_end_pts is not None and state.tv_pts - state.last_overlay_end_pts < MIN_GAP_MS:
        return Constraint.MIN_GAP
    if candidate.partisan and state.both_clubs_present:
        return Constraint.NEUTRAL_FRAMING
    return None


def asked_for(bids: list[Bid], candidate_id: str) -> list[str]:
    """Fans whose agent asked for an overlay: they wanted it at least half as much as their favourite.

    This is the count the TV shows ("3 of 4 in the room asked for this"), so it counts real wishes, not
    every overlay an agent put a small value on.
    """
    favourite: dict[str, float] = defaultdict(float)
    for bid in bids:
        favourite[bid.agent_id] = max(favourite[bid.agent_id], bid.utility)
    return sorted(
        b.agent_id
        for b in bids
        if b.candidate_id == candidate_id and b.utility > 0 and b.utility >= 0.5 * favourite[b.agent_id]
    )


def within_budget(bids: list[Bid]) -> list[Bid]:
    """Scales each agent's bids down so they add up to at most BID_BUDGET. Bids already within it are kept."""
    totals: dict[str, float] = defaultdict(float)
    for bid in bids:
        totals[bid.agent_id] += bid.utility
    return [
        Bid(b.agent_id, b.candidate_id, b.utility * min(1.0, BID_BUDGET / totals[b.agent_id]))
        if totals[b.agent_id] > 0
        else b
        for b in bids
    ]


def sanitise(bids: list[Bid], state: RoomState) -> list[Bid]:
    """Bids can arrive over A2A from agents the broadcaster doesn't run, so the Director trusts nothing it is
    sent: utilities are held to 0-1 (a negative bid would otherwise free budget for a bigger one), and bids
    from agents that aren't in the room are dropped."""
    room = set(state.agent_ids)
    return [
        Bid(b.agent_id, b.candidate_id, min(max(b.utility, 0.0), 1.0)) for b in bids if b.agent_id in room
    ]


def decide(candidates: list[Candidate], bids: list[Bid], state: RoomState) -> Decision:
    started = perf_counter()
    bids = within_budget(sanitise(bids, state))
    weights = {
        agent: fairness_weight(state.seconds_without_screen.get(agent, 0.0)) for agent in state.agent_ids
    }

    raw: dict[str, float] = defaultdict(float)
    fair: dict[str, float] = defaultdict(float)
    for bid in bids:
        raw[bid.candidate_id] += bid.utility
        fair[bid.candidate_id] += weights.get(bid.agent_id, 1.0) * bid.utility

    struck = {c.id: strike(c, state) for c in candidates}
    eligible = [c for c in candidates if struck[c.id] is None and fair[c.id] > 0]
    # Ties go to the earlier moment, then to the id, so the same inputs always give the same answer.
    winner = max(eligible, key=lambda c: (fair[c.id], -c.pts, c.id), default=None)
    winner_id = winner.id if winner else None

    return Decision(
        pts=state.tv_pts,
        weights=[
            Weight(agent, weights[agent], state.seconds_without_screen.get(agent, 0.0))
            for agent in state.agent_ids
        ],
        candidates=[
            Scored(
                c.id,
                round(raw[c.id], 4),
                round(fair[c.id], 4),
                struck[c.id],
                c.id == winner_id,
                tuple(asked_for(bids, c.id)),
            )
            for c in candidates
        ],
        winner=winner_id,
        delivered_privately=_private_deliveries(bids, winner_id),
        decided_in_ms=(perf_counter() - started) * 1000,
    )


def _private_deliveries(bids: list[Bid], winner_id: str | None) -> dict[str, str]:
    """Each fan whose favourite didn't make the TV gets it on their own phone instead."""
    favourite: dict[str, Bid] = {}
    for bid in bids:
        current = favourite.get(bid.agent_id)
        if current is None or bid.utility > current.utility:
            favourite[bid.agent_id] = bid
    return {agent: bid.candidate_id for agent, bid in favourite.items() if bid.candidate_id != winner_id}
