"""Does the Room Director share the TV fairly? Ten thousand simulated living rooms, each through one match.

Every room gets two to five fans with random clubs and tastes. At each overlay moment the room is offered
three neutral overlays (a story, both teams' shape, a stat) and one that favours each club. Every fan's agent
bids by its taste, and the TV is decided
twice: by the Director, and by a baseline where the loudest total bid wins with no house rules. We measure:

- neutral violations: a one-club overlay on the TV while both clubs are in the room (should be zero);
- served: a fan is served at a moment when the TV shows something they wanted at least half as much as
  their favourite. Their favourite always reaches their own phone either way;
- worst-off fan: the share of moments the least-served fan in each room was served (higher is fairer);
- longest wait: the longest run of moments a fan went unserved;
- never served: share of fans the TV never served all match;
- favourite reached: share of fan-moments where the fan's favourite pick reached them, on the TV or, after
  it, on their own phone (the Director only).

    python -m frontroom_agents.evals.fairness --rooms 10000
"""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from ..room.director import Bid, Candidate, RoomState, decide

MOMENTS_PER_MATCH = 12
SECONDS_BETWEEN_MOMENTS = 360
CLUBS = ("kestrel", "ashvale")


NEUTRAL_KINDS = ("story", "shape", "stat")


@dataclass(frozen=True)
class Fan:
    id: str
    club: str
    taste: dict[str, float]
    loyalty: float


def random_room(rng: random.Random) -> list[Fan]:
    return [
        Fan(f"fan{i}", rng.choice(CLUBS), {k: rng.random() for k in NEUTRAL_KINDS}, rng.uniform(0.3, 1.0))
        for i in range(rng.randint(2, 5))
    ]


def moment(index: int) -> list[Candidate]:
    pts = index * SECONDS_BETWEEN_MOMENTS * 1000
    return [Candidate(f"m{index}-{kind}", pts, partisan=False) for kind in NEUTRAL_KINDS] + [
        Candidate(f"m{index}-{club}", pts, partisan=True) for club in CLUBS
    ]


def bids_for(fan: Fan, candidates: list[Candidate], rng: random.Random) -> list[Bid]:
    """Neutral overlays by taste; their own club's overlay by loyalty; the rival's barely at all."""
    bids = []
    for c in candidates:
        kind = c.id.split("-", 1)[1]
        if not c.partisan:
            utility = fan.taste[kind]
        elif kind == fan.club:
            utility = max(fan.taste["shape"], fan.loyalty)
        else:
            utility = 0.05
        bids.append(Bid(fan.id, c.id, max(0.0, min(1.0, utility + rng.gauss(0, 0.1)))))
    return bids


def loudest_wins(candidates: list[Candidate], bids: list[Bid], state: RoomState) -> str | None:
    totals = {c.id: sum(b.utility for b in bids if b.candidate_id == c.id) for c in candidates}
    return max(totals, key=totals.get) if totals else None


def director(candidates: list[Candidate], bids: list[Bid], state: RoomState) -> str | None:
    return decide(candidates, bids, state).winner


def gini(values: list[float]) -> float:
    ordered = sorted(values)
    n, total = len(ordered), sum(ordered)
    if total == 0:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(ordered)) / (n * total)


Policy = Callable[[list[Candidate], list[Bid], RoomState], str | None]


def run(policy: Policy, rooms: int, seed: int) -> dict:
    rng = random.Random(seed)
    violations = decisions = never = fans_total = 0
    worst_off: list[float] = []
    longest_waits: list[int] = []
    ginis: list[float] = []
    for _ in range(rooms):
        fans = random_room(rng)
        both = len({f.club for f in fans}) > 1
        served = {f.id: 0 for f in fans}
        waiting = {f.id: 0 for f in fans}
        longest = {f.id: 0 for f in fans}
        for index in range(MOMENTS_PER_MATCH):
            candidates = moment(index)
            bids = [b for f in fans for b in bids_for(f, candidates, rng)]
            state = RoomState(
                agent_ids=[f.id for f in fans],
                both_clubs_present=both,
                tv_pts=candidates[0].pts,
                seconds_without_screen={f: w * SECONDS_BETWEEN_MOMENTS for f, w in waiting.items()},
            )
            winner = policy(candidates, bids, state)
            decisions += 1
            if winner and both and next(c for c in candidates if c.id == winner).partisan:
                violations += 1
            for f in fans:
                mine = {b.candidate_id: b.utility for b in bids if b.agent_id == f.id}
                if winner and mine.get(winner, 0.0) >= 0.5 * max(mine.values()):
                    served[f.id] += 1
                    waiting[f.id] = 0
                else:
                    waiting[f.id] += 1
                    longest[f.id] = max(longest[f.id], waiting[f.id])
        worst_off.append(min(served.values()) / MOMENTS_PER_MATCH)
        longest_waits.extend(longest.values())
        ginis.append(gini([float(v) for v in served.values()]))
        never += sum(1 for v in served.values() if v == 0)
        fans_total += len(fans)
    waits = sorted(longest_waits)
    return {
        "rooms": rooms,
        "decisions": decisions,
        "neutral_violations": violations,
        "worst_off_fan_served": round(mean(worst_off), 3),
        "longest_wait_median": waits[len(waits) // 2],
        "longest_wait_p95": waits[int(len(waits) * 0.95)],
        "served_gini": round(mean(ginis), 3),
        "never_served": round(never / fans_total, 3),
    }


def favourite_reached(rooms: int, seed: int) -> dict:
    """How often each fan's own favourite pick reached them: on the TV, or privately on their phone."""
    rng = random.Random(seed)
    reached = total = 0
    for _ in range(rooms):
        fans = random_room(rng)
        both = len({f.club for f in fans}) > 1
        for index in range(MOMENTS_PER_MATCH):
            candidates = moment(index)
            bids = [b for f in fans for b in bids_for(f, candidates, rng)]
            state = RoomState(
                agent_ids=[f.id for f in fans], both_clubs_present=both, tv_pts=candidates[0].pts
            )
            decision = decide(candidates, bids, state)
            for f in fans:
                favourite = max((b for b in bids if b.agent_id == f.id), key=lambda b: b.utility).candidate_id
                total += 1
                reached += favourite in (decision.winner, decision.delivered_privately.get(f.id))
    return {"fan_moments": total, "favourite_reached": reached, "share": round(reached / total, 4)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rooms", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("fairness-results.json"))
    args = parser.parse_args()
    results = {
        "director": run(director, args.rooms, args.seed),
        "loudest_wins": run(loudest_wins, args.rooms, args.seed),
        "moments_per_match": MOMENTS_PER_MATCH,
        "favourite_reached": favourite_reached(args.rooms, args.seed),
    }
    args.out.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
