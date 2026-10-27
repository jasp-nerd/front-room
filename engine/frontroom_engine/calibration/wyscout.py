"""Event-level reference statistics from the Wyscout public Premier League 2017/18 data.

Wyscout logs a duel twice (one event per player) and has no carry or pressure events, so the
action count uses one event per duel and leaves those out. `metrics.ACTION_TYPES` is the
matching definition on the synthetic side.
"""

import json
import math
from collections import Counter, defaultdict
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from frontroom_engine.calibration.definitions import PASS_LENGTH_BANDS, pass_band, quantiles

ACCURATE = 1801
GOAL = 101
YELLOW = 1702
SECOND_YELLOW = 1703
ACTION_EVENTS = {"Pass", "Free Kick", "Shot", "Others on the ball", "Save attempt", "Foul"}


def _tags(event: dict[str, Any]) -> set[int]:
    return {tag["id"] for tag in event["tags"]}


def _metres(start: dict[str, float], end: dict[str, float]) -> float:
    return math.hypot((end["x"] - start["x"]) * 1.05, (end["y"] - start["y"]) * 0.68)


def _pass_stats(passes: list[dict[str, Any]], n_matches: int) -> dict[str, Any]:
    lengths: list[float] = []
    band_total: Counter[str] = Counter()
    band_accurate: Counter[str] = Counter()
    for event in passes:
        positions = event["positions"]
        if len(positions) < 2 or (positions[1]["x"] == 0 and positions[1]["y"] == 0):
            continue
        length = _metres(positions[0], positions[1])
        lengths.append(length)
        band = pass_band(length)
        band_total[band] += 1
        band_accurate[band] += ACCURATE in _tags(event)
    accurate = sum(ACCURATE in _tags(event) for event in passes)
    return {
        "passes_per_match": len(passes) / n_matches,
        "pass_accuracy": accurate / len(passes),
        "pass_accuracy_by_length": {
            name: band_accurate[name] / band_total[name] for name, _, _ in PASS_LENGTH_BANDS
        },
        "pass_length_m": quantiles(lengths),
    }


def _shot_stats(shots: list[dict[str, Any]], n_matches: int) -> dict[str, Any]:
    distances = [
        math.hypot((100 - s["positions"][0]["x"]) * 1.05, (50 - s["positions"][0]["y"]) * 0.68) for s in shots
    ]
    goals = sum(GOAL in _tags(shot) for shot in shots)
    return {
        "shots_per_match": len(shots) / n_matches,
        "shot_conversion": goals / len(shots),
        "shot_distance_m": quantiles(distances),
    }


def _gap_stats(by_match: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    gaps: list[float] = []
    actions_per_match: list[float] = []
    for events in by_match.values():
        actions = sorted(
            (e for e in events if e["eventName"] in ACTION_EVENTS or e["eventName"] == "Duel"),
            key=lambda e: (e["matchPeriod"], e["eventSec"]),
        )
        duels = sum(e["eventName"] == "Duel" for e in actions)
        actions_per_match.append(len(actions) - duels / 2)
        for previous, current in pairwise(actions):
            if previous["matchPeriod"] == current["matchPeriod"]:
                gaps.append(current["eventSec"] - previous["eventSec"])
    return {
        "actions_per_match": float(np.mean(actions_per_match)),
        "actions_per_match_sd": float(np.std(actions_per_match)),
        "inter_event_gap_s": quantiles([g for g in gaps if g > 0]),
    }


def _result_stats(matches: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes: Counter[str] = Counter()
    goals: list[int] = []
    for match in matches:
        sides = {team["side"]: team["score"] for team in match["teamsData"].values()}
        goals.append(sides["home"] + sides["away"])
        outcomes[
            "home" if sides["home"] > sides["away"] else "away" if sides["away"] > sides["home"] else "draw"
        ] += 1
    return {
        "goals_per_match": float(np.mean(goals)),
        "goals_per_match_sd": float(np.std(goals)),
        "results": {key: outcomes[key] / len(matches) for key in ("home", "draw", "away")},
    }


def wyscout_reference(events_path: Path, matches_path: Path) -> dict[str, Any]:
    """Compute the event reference statistics from the raw Wyscout England files."""
    events: list[dict[str, Any]] = json.loads(events_path.read_text())
    matches: list[dict[str, Any]] = json.loads(matches_path.read_text())
    by_match: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_match[event["matchId"]].append(event)
    n_matches = len(by_match)
    counts = Counter(event["eventName"] for event in events)
    sub_counts = Counter(event["subEventName"] for event in events)

    def per_match(count: float) -> float:
        return count / n_matches

    return {
        "source": "Wyscout public dataset, Premier League 2017/18 (CC BY 4.0)",
        "matches": n_matches,
        **_gap_stats(by_match),
        **_pass_stats([e for e in events if e["eventName"] == "Pass"], n_matches),
        **_shot_stats([e for e in events if e["eventName"] == "Shot"], n_matches),
        **_result_stats(matches),
        "fouls_per_match": per_match(counts["Foul"]),
        "yellow_cards_per_match": per_match(
            sum(YELLOW in _tags(e) or SECOND_YELLOW in _tags(e) for e in events)
        ),
        "corners_per_match": per_match(sub_counts["Corner"]),
        "throw_ins_per_match": per_match(sub_counts["Throw in"]),
        "offsides_per_match": per_match(counts["Offside"]),
    }
