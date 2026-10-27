"""A SynthLeague match from the engine, as the room server plays it.

    load_match(Path("data/generated/demo"))

Reads the engine's four files: the event feed (with the amendment that VAR wrote), the metadata, and the
truth file, from which each shot's physical xG is copied onto its event so the value model can price the
finish. A goal that VAR ruled out is not a goal.
"""

from __future__ import annotations

import json
from pathlib import Path

from .show import Goal, MatchSource

HALF_TIME_MS = 15 * 60_000
CLUBS = {"KES": "kestrel", "ASH": "ashvale"}


def stream_pts(metadata: dict, period: int, clock_ms: int) -> int:
    """Milliseconds from kick-off of the broadcast, with a 15-minute half-time between the periods."""
    if period == 1:
        return clock_ms
    first_half = next(p["durationMs"] for p in metadata["periods"] if p["period"] == 1)
    return first_half + HALF_TIME_MS + clock_ms


def match_clock(period: int, clock_ms: int) -> str:
    """The clock as a scorebug shows it: 61:41 for 16:41 into the second half."""
    seconds = clock_ms // 1000 + (45 * 60 if period == 2 else 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


def load_match(directory: Path) -> MatchSource:
    metadata = json.loads((directory / "metadata.json").read_text())
    truth = json.loads((directory / "truth.json").read_text())
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines() if line]

    xg = {shot["eventId"]: shot["xg"] for shot in truth["shots"]}
    for event in events:
        if event["id"] in xg:
            event.setdefault("detail", {})["xg"] = xg[event["id"]]

    players = {
        p["playerId"]: p["shortName"].split(". ")[-1]
        for side in ("home", "away")
        for p in metadata[side]["squad"]
    }
    club = {
        side: CLUBS.get(metadata[side]["short"], metadata[side]["short"].lower()) for side in ("home", "away")
    }

    ruled_out = {e["amends"] for e in events if e.get("amends")}
    goals = []
    for goal in (
        e for e in events if e["type"] == "goal" and e["id"] not in ruled_out and not e.get("amends")
    ):
        shot = next(e for e in reversed(events) if e["type"] == "shot" and e["seq"] < goal["seq"])
        conceding = "away" if goal["side"] == "home" else "home"
        goals.append(
            Goal(
                shot_id=shot["id"],
                pts=stream_pts(metadata, goal["period"], goal["clockMs"]),
                scoring_club=club[goal["side"]],
                conceding_club=club[conceding],
                attacking_right=shot.get("end", shot["start"])["x"] > shot["start"]["x"],
            )
        )
    story_goal = next(
        (b["events"]["goalEvent"] for b in truth.get("story", []) if b["beat"] == "okafor_goal"), None
    )
    goal_ids = [
        g["id"] for g in events if g["type"] == "goal" and g["id"] not in ruled_out and not g.get("amends")
    ]
    featured = goal_ids.index(story_goal) if story_goal in goal_ids else 0
    return MatchSource(metadata["matchId"], events, players, goals, featured)
