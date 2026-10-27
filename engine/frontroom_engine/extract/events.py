"""Turn the simulator's action log into a feed of `match-event` records, with labelling noise.

Real event data is produced by human operators: coordinates sit on a coarse grid, timestamps
wobble, some pressures are never logged and some crosses are called passes. Adding the same
kinds of error keeps models trained on this feed honest. The noise is seeded per action, so
the same match always yields the same feed.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np

from frontroom_engine.pitch import PITCH_LENGTH, PITCH_WIDTH
from frontroom_engine.sim.records import Action

GRID_X = PITCH_LENGTH / 100
GRID_Y = PITCH_WIDTH / 100
POSITION_NOISE = 0.7
CLOCK_NOISE_MS = 150
MISSED_PRESS = 0.12
CROSS_CALLED_PASS = 0.05
LABEL_DOMAIN = 3
NO_PLAYER = ("var_check", "var_decision")


@dataclass(frozen=True)
class Feed:
    events: list[dict[str, Any]]
    event_ids: dict[int, str]
    """Simulator action id -> feed event id, for linking latent truth to the feed."""


def _labelled_point(xy: tuple[float, float], rng: np.random.Generator) -> dict[str, float]:
    x = np.clip(xy[0] + POSITION_NOISE * rng.standard_normal(), 0.0, PITCH_LENGTH)
    y = np.clip(xy[1] + POSITION_NOISE * rng.standard_normal(), 0.0, PITCH_WIDTH)
    return {
        "x": round(float(np.round(x / GRID_X) * GRID_X), 2),
        "y": round(float(np.round(y / GRID_Y) * GRID_Y), 2),
    }


def _event(
    match_id: str, seq: int, action: Action, rng: np.random.Generator, keep: bool
) -> dict[str, Any] | None:
    kind = action.kind
    if kind == "press" and rng.random() < MISSED_PRESS and not keep:
        return None
    if kind == "cross" and rng.random() < CROSS_CALLED_PASS:
        kind = "pass"
    clock = max(0, action.clock_ms + int(CLOCK_NOISE_MS * rng.standard_normal()))
    event: dict[str, Any] = {
        "id": f"ev-{seq:05d}",
        "matchId": match_id,
        "seq": seq,
        "period": action.period,
        "clockMs": clock,
        "side": "home" if action.team == 0 else "away",
        "type": kind,
        "result": action.result,
        "start": _labelled_point(action.start, rng),
    }
    if kind not in NO_PLAYER:
        event["playerId"] = action.player_id
    if action.end is not None:
        event["end"] = _labelled_point(action.end, rng)
    if kind in ("pass", "cross", "shot", "clearance", "penalty", "throw_in", "keeper_save"):
        event["bodyPart"] = action.body_part
    detail = {key: value for key, value in action.detail.items() if not key.endswith("Action")}
    detail["possession"] = action.possession
    event["detail"] = detail
    return event


def _amendment(goal: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """A disallowed goal is corrected, not deleted: same seq, new id, pointing at the original."""
    return {
        **goal,
        "id": f"{goal['id']}-a",
        "clockMs": decision["clockMs"],
        "result": "none",
        "detail": {**goal["detail"], "disallowed": True, "reason": decision["detail"].get("reason", "var")},
        "amends": goal["id"],
    }


def extract_events(
    match_id: str, seed: int, actions: Iterable[Action], keep: frozenset[int] = frozenset()
) -> Feed:
    """Build the feed in match order. Amendments reuse the seq of the event they correct.

    Actions in `keep` (a storyline's key moments) are never dropped by labelling noise.
    """
    events: list[dict[str, Any]] = []
    event_ids: dict[int, str] = {}
    seq = 0
    for action in sorted(actions, key=lambda a: (a.tick, a.id)):
        rng = np.random.default_rng([seed, action.id, LABEL_DOMAIN])
        event = _event(match_id, seq, action, rng, action.id in keep)
        if event is None:
            continue
        seq += 1
        events.append(event)
        event_ids[action.id] = event["id"]
        goal_action = action.detail.get("goalAction")
        if goal_action in event_ids:
            goal_id = event_ids[int(goal_action)]
            event["detail"]["goalEvent"] = goal_id
            if action.kind == "var_decision" and action.result == "offside":
                original = next(e for e in events if e["id"] == goal_id)
                events.append(_amendment(original, event))
    return Feed(events, event_ids)
