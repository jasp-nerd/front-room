"""Credit for a goal, action by action: how much each on-ball action changed the chance of scoring,
compared with what a typical player would have done from the same spot.

Values are in expected-threat units (see xt.py). A goal gets a single "decisive" action only when one action
clearly did more than any other: it must add at least DECISIVE_FLOOR and its interval must sit above the
runner-up's. Otherwise the credit is shared, and we say so rather than pick a winner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .xt import PITCH_LENGTH, PITCH_WIDTH, ExpectedThreat

DECISIVE_FLOOR = 0.05
MOVES = {"pass", "cross", "dribble", "take_on"}
REGAINS = {"tackle", "interception", "press"}
SHOTS = {"shot", "penalty"}

Event = dict[str, Any]


@dataclass(frozen=True)
class Credit:
    event_id: str
    player_id: str | None
    type: str
    value: float
    low: float
    high: float


@dataclass(frozen=True)
class Verdict:
    kind: Literal["decisive", "shared"]
    top: Credit
    runner_up: Credit | None


def scoring_possession(events: list[Event], shot_id: str) -> list[Event]:
    """The scoring team's actions from the pressing that won the ball back up to the shot, in order.

    The defending team keeps pressing during a possession, so their presses never end it: only one of their
    actions on the ball does. When the feed numbers its possessions, the scoring team's possession is taken
    as the feed records it. Either way the chain then reaches back over the regain (a tackle or an
    interception) and the presses that forced it, which the feed files under the possession they ended.
    """
    by_id = {e["id"]: e for e in events}
    shot = by_id[shot_id]
    side = shot["side"]
    ordered = [e for e in sorted(events, key=lambda e: e["seq"]) if e["period"] == shot["period"]]
    before = [e for e in ordered if e["seq"] <= shot["seq"]]
    possession = shot.get("detail", {}).get("possession")

    chain: list[Event] = []
    rest = list(reversed(before))
    while rest:
        event = rest[0]
        if possession is not None and event.get("detail", {}).get("possession") != possession:
            break
        # Without possession numbers, any defending action on the ball ends the possession. With them, the
        # feed has already decided: a tackle that didn't win it or a foul stays inside the possession.
        if possession is None and event["side"] != side and event["type"] != "press":
            break
        rest.pop(0)
        if event["side"] == side:
            chain.append(event)
        if (
            possession is None
            and event["side"] == side
            and event["type"] in REGAINS
            and event["result"] == "success"
        ):
            return list(reversed(chain))

    # Reach back over the regain and the pressing that forced it, until the other team was on the ball.
    for event in rest:
        if event["side"] != side:
            if event["type"] == "press":
                continue
            break
        if event["type"] in REGAINS:
            chain.append(event)
        else:
            break
    return list(reversed(chain))


def _attacking(point: dict, attacking_right: bool) -> tuple[float, float]:
    """Pitch metres as the attacking team sees them: towards x = 105, their left at y = 68."""
    if attacking_right:
        return point["x"], point["y"]
    return PITCH_LENGTH - point["x"], PITCH_WIDTH - point["y"]


def _value(event: Event, at, attacking_right: bool) -> np.ndarray | float:
    """The value an action adds against typical play, using `at(x, y)` for the threat at a spot."""
    x, y = _attacking(event["start"], attacking_right)
    kind, success = event["type"], event["result"] == "success"
    if kind in MOVES:
        if not success or "end" not in event:
            return -at(x, y)
        ex, ey = _attacking(event["end"], attacking_right)
        return at(ex, ey) - at(x, y)
    if kind in REGAINS and success:
        # Winning the ball here starts our threat from this spot and ends theirs from the mirrored spot.
        return at(x, y) + at(PITCH_LENGTH - x, PITCH_WIDTH - y)
    if kind in SHOTS:
        xg = float(event.get("detail", {}).get("xg", 0.0))
        return xg - at(x, y)
    return 0.0


def credit(chain: list[Event], model: ExpectedThreat, attacking_right: bool) -> list[Credit]:
    credits = []
    for event in chain:
        value = float(_value(event, model.at, attacking_right))
        samples = np.asarray(_value(event, model.samples_at, attacking_right)) * np.ones(len(model.samples))
        low, high = (round(float(q), 4) for q in np.percentile(samples, [5, 95]))
        credits.append(Credit(event["id"], event.get("playerId"), event["type"], round(value, 4), low, high))
    return credits


def verdict(credits: list[Credit]) -> Verdict:
    """Decisive only if the top action clears the floor and its interval sits above the runner-up's."""
    ranked = sorted((c for c in credits if c.type not in SHOTS), key=lambda c: c.value, reverse=True)
    if not ranked:
        # A rebound or a scramble: the shot is the whole possession, and nothing before it can be credited.
        return Verdict("shared", credits[-1], None)
    top = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    clear = runner_up is None or top.low > runner_up.high
    kind: Literal["decisive", "shared"] = "decisive" if top.value >= DECISIVE_FLOOR and clear else "shared"
    return Verdict(kind, top, runner_up)
