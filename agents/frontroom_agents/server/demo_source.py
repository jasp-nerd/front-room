"""The demo match the server plays until it is pointed at a SynthLeague match from the engine.

One goal: Kestrel (home, attacking right in the second half) win the ball back on halfway, three passes, and
Okafor scores. Positions match the TV's origin frame.
"""

from __future__ import annotations

from pathlib import Path

from .engine_source import load_match
from .show import Goal, MatchSource

GOAL_PTS = 3_792_000


def _event(seq: int, side: str, player: str, type_: str, start, end=None, **detail) -> dict:
    event = {
        "id": f"ev-{1840 + seq}",
        "matchId": "demo-kes-ash",
        "seq": 1840 + seq,
        "period": 2,
        "clockMs": 1_074_000 + seq * 2_000,
        "side": side,
        "playerId": player,
        "type": type_,
        "result": "success",
        "start": {"x": start[0], "y": start[1]},
    }
    if end:
        event["end"] = {"x": end[0], "y": end[1]}
    if detail:
        event["detail"] = detail
    return event


EVENTS = [
    _event(0, "away", "ash-5", "pass", (50, 30), (56.8, 28.6)),
    _event(1, "home", "kes-6", "press", (56.5, 29.5)),
    _event(2, "home", "kes-6", "pass", (56.5, 29.5), (63, 21)),
    _event(3, "home", "kes-7", "pass", (63, 21), (77, 27)),
    _event(4, "home", "kes-8", "pass", (77, 27), (88, 37)),
    _event(5, "home", "kes-9", "shot", (88, 37), (103.6, 33.4), xg=0.11),
]

PLAYERS = {
    "kes-6": "Mensah",
    "kes-7": "Ito",
    "kes-8": "Vidal",
    "kes-9": "Okafor",
    "ash-4": "Lund",
    "ash-5": "Rios",
}


# What each fan in the demo room types when they join, in their own words.
DEMO_FANS = {
    "rob": "Kestrel fan. Show me the shape, I want numbers. Pass accuracy is my thing.",
    "ana": "Soy de Ashvale. Solo lo importante, en español por favor. Y la posesión.",
    "leo": "I'm 10 and I like goals. Okafor is my favourite, he's the fastest!",
    "sam": "Kestrel. Big text, talk me through it.",
}


# The engine's demo match (Kestrel FC v Ashvale Athletic), copied here from the engine's output so
# the server image carries it. Without it the hand-made goal above is used.
DEMO_MATCH = Path(__file__).with_name("demo_match")


def demo_source() -> MatchSource:
    if (DEMO_MATCH / "events.jsonl").exists():
        return load_match(DEMO_MATCH)
    goal = Goal("ev-1845", GOAL_PTS, "kestrel", "ashvale", attacking_right=True)
    return MatchSource("demo-kes-ash", EVENTS, PLAYERS, [goal])
