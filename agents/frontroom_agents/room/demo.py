"""The demo room: four fans, two clubs, one goal, and three overlays that want the TV.

Run `python -m frontroom_agents.room.demo` to print the Director's decision as protocol JSON. The web app's
room view and phone fixtures are generated from this output, so what the demo shows is what the Director did.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace

from .director import Bid, Candidate, RoomState, decide
from .wire import decision_to_wire

ROOM_ID = "room-demo"
GOAL_PTS = 3_792_000

WHERE_IT_STARTED = Candidate("where-it-started", GOAL_PTS, partisan=False)
PRESSING_MAP = Candidate("kestrel-pressing-map", GOAL_PTS, partisan=True)
KEEPERS_VIEW = Candidate("keepers-view", GOAL_PTS, partisan=True)
CANDIDATES = [WHERE_IT_STARTED, PRESSING_MAP, KEEPERS_VIEW]


def front_room(**overrides: object) -> RoomState:
    state = RoomState(
        agent_ids=["rob", "ana", "leo", "sam"],
        both_clubs_present=True,
        tv_pts=GOAL_PTS + 4_000,
        seconds_without_screen={"rob": 60, "ana": 120, "leo": 540, "sam": 300},
    )
    return replace(state, **overrides)


def demo_bids() -> list[Bid]:
    return [
        Bid("rob", PRESSING_MAP.id, 0.95),
        Bid("ana", KEEPERS_VIEW.id, 0.90),
        Bid("ana", WHERE_IT_STARTED.id, 0.55),
        Bid("leo", WHERE_IT_STARTED.id, 0.70),
        Bid("leo", PRESSING_MAP.id, 0.55),
        Bid("sam", WHERE_IT_STARTED.id, 0.45),
        Bid("sam", PRESSING_MAP.id, 0.65),
    ]


def bids_to_wire(bids: list[Bid], room_id: str, placed_at_pts: int) -> list[dict[str, object]]:
    partisan = {c.id: c.partisan for c in CANDIDATES}
    return [
        {
            "roomId": room_id,
            "agentId": b.agent_id,
            "candidateId": b.candidate_id,
            "utility": b.utility,
            "partisan": partisan[b.candidate_id],
            "placedAtPts": placed_at_pts,
        }
        for b in bids
    ]


def main() -> None:
    state = front_room()
    bids = demo_bids()
    decision = decide(CANDIDATES, bids, state)
    json.dump(
        {
            "bids": bids_to_wire(bids, ROOM_ID, GOAL_PTS + 1_500),
            "decision": decision_to_wire(decision, ROOM_ID, "decision-goal-1"),
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
