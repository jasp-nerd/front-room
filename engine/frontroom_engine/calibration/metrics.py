"""Statistics of simulated matches, defined to mirror `wyscout.py` and `idsse.py`.

`match_metrics` reduces one match to raw ingredients (lists of pass lengths, gaps, per-player
physical totals); `summarise` pools them across matches into the same shape as the reference.
"""

import math
from collections import Counter
from itertools import pairwise
from typing import Any

import numpy as np

from frontroom_engine.calibration.definitions import (
    FULL_MATCH_MINUTES,
    HIGH_SPEED_KMH,
    PASS_LENGTH_BANDS,
    count_sprints,
    pass_band,
    quantiles,
    speed_band_shares,
)
from frontroom_engine.extract.tracking import FRAME_RATE, Tracking
from frontroom_engine.pitch import CENTRE_Y, PITCH_LENGTH

ACTION_TYPES = {
    "pass",
    "cross",
    "throw_in",
    "corner",
    "free_kick",
    "goal_kick",
    "take_on",
    "shot",
    "penalty",
    "keeper_save",
    "tackle",
    "interception",
    "clearance",
    "foul",
}
OPEN_PLAY_PASSES = {"pass", "cross"}
SHAPE_SAMPLE_EVERY = 25
KEEPER_SLOTS = (0, 11)


def _attacked_goal_x(event: dict[str, Any]) -> float:
    home_attacks_right = event["period"] == 1
    return PITCH_LENGTH if (event["side"] == "home") == home_attacks_right else 0.0


def event_metrics(events: list[dict[str, Any]], score: tuple[int, int]) -> dict[str, Any]:
    feed = [e for e in events if "amends" not in e]
    actions = sorted(
        (e for e in feed if e["type"] in ACTION_TYPES), key=lambda e: (e["period"], e["clockMs"])
    )
    gaps = [
        (b["clockMs"] - a["clockMs"]) / 1000
        for a, b in pairwise(actions)
        if a["period"] == b["period"] and b["clockMs"] > a["clockMs"]
    ]
    passes = [
        (
            math.dist((e["start"]["x"], e["start"]["y"]), (e["end"]["x"], e["end"]["y"])),
            e["result"] == "success",
        )
        for e in feed
        if e["type"] in OPEN_PLAY_PASSES and "end" in e
    ]
    shots = [
        (
            math.hypot(_attacked_goal_x(e) - e["start"]["x"], CENTRE_Y - e["start"]["y"]),
            e["result"] == "success",
        )
        for e in feed
        if e["type"] == "shot" and "setPiece" not in e["detail"]
    ]
    types = Counter(e["type"] for e in feed)
    cards = Counter(e["detail"].get("colour") for e in feed if e["type"] == "card")
    home, away = score
    return {
        "actions": len(actions),
        "gaps": gaps,
        "passes": passes,
        "shots": shots,
        "goals": home + away,
        "result": "home" if home > away else "away" if away > home else "draw",
        "fouls": types["foul"],
        "yellow_cards": cards["yellow"] + cards["second_yellow"],
        "corners": types["corner"],
        "throw_ins": types["throw_in"],
        "offsides": sum(
            e["result"] == "offside" for e in feed if e["type"] in ("pass", "cross", "free_kick")
        ),
    }


def tracking_metrics(tracking: Tracking) -> dict[str, Any]:
    speeds_kmh = tracking.speed * 3.6
    per_player: dict[int, list[np.ndarray]] = {}
    for slot in range(tracking.roster.shape[1]):
        if slot in KEEPER_SLOTS:
            continue
        for player in np.unique(tracking.roster[:, slot]):
            if player >= 0:
                per_player.setdefault(int(player), []).append(
                    speeds_kmh[tracking.roster[:, slot] == player, slot]
                )
    full = [np.concatenate(parts) for parts in per_player.values()]
    full = [s for s in full if len(s) / FRAME_RATE / 60 > FULL_MATCH_MINUTES]
    lengths, widths = [], []
    sampled = np.flatnonzero(tracking.alive)[::SHAPE_SAMPLE_EVERY]
    for team in (0, 1):
        outfield = [slot for slot in range(11 * team + 1, 11 * team + 11)]
        present = tracking.roster[sampled][:, outfield] >= 0
        xs = np.where(present, tracking.pos[sampled][:, outfield, 0], np.nan)
        ys = np.where(present, tracking.pos[sampled][:, outfield, 1], np.nan)
        lengths.extend(np.nanmax(xs, 1) - np.nanmin(xs, 1))
        widths.extend(np.nanmax(ys, 1) - np.nanmin(ys, 1))
    ball_step = np.linalg.norm(np.diff(tracking.ball, axis=0), axis=1) * FRAME_RATE * 3.6
    continuous = (np.diff(tracking.period) == 0) & tracking.alive[1:]
    return {
        "distance_km": [float(np.sum(s) / 3.6 / FRAME_RATE / 1000) for s in full],
        "top_speed_kmh": [float(np.max(s)) for s in full],
        "sprints": [count_sprints(s, FRAME_RATE) for s in full],
        "high_speed_m": [float(np.sum(s[s >= HIGH_SPEED_KMH]) / 3.6 / FRAME_RATE) for s in full],
        "speed_band_shares": speed_band_shares(np.concatenate(full)),
        "ball_in_play_share": float(tracking.alive.mean()),
        "ball_speed_kmh": quantiles(ball_step[continuous]),
        "team_length_m": float(np.median(lengths)),
        "team_width_m": float(np.median(widths)),
    }


def _band_accuracy(passes: list[tuple[float, bool]]) -> dict[str, float]:
    totals: Counter[str] = Counter()
    hits: Counter[str] = Counter()
    for length, success in passes:
        band = pass_band(length)
        totals[band] += 1
        hits[band] += success
    return {
        name: hits[name] / totals[name] if totals[name] else float("nan") for name, _, _ in PASS_LENGTH_BANDS
    }


def summarise(event_parts: list[dict[str, Any]], tracking_parts: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool per-match ingredients into the reference shape (`events` and `tracking` sections)."""
    n = len(event_parts)
    passes = [p for m in event_parts for p in m["passes"]]
    shots = [s for m in event_parts for s in m["shots"]]
    results = Counter(m["result"] for m in event_parts)

    def mean(key: str) -> float:
        return float(np.mean([m[key] for m in event_parts]))

    events = {
        "matches": n,
        "actions_per_match": mean("actions"),
        "inter_event_gap_s": quantiles([g for m in event_parts for g in m["gaps"]]),
        "passes_per_match": len(passes) / n,
        "pass_accuracy": float(np.mean([success for _, success in passes])),
        "pass_accuracy_by_length": _band_accuracy(passes),
        "pass_length_m": quantiles([length for length, _ in passes]),
        "shots_per_match": len(shots) / n,
        "shot_conversion": float(np.mean([goal for _, goal in shots])) if shots else 0.0,
        "shot_distance_m": quantiles([d for d, _ in shots]) if shots else {},
        "goals_per_match": mean("goals"),
        "results": {key: results[key] / n for key in ("home", "draw", "away")},
        **{
            f"{key}_per_match": mean(key)
            for key in ("fouls", "yellow_cards", "corners", "throw_ins", "offsides")
        },
    }
    pooled = {
        k: [v for m in tracking_parts for v in m[k]]
        for k in ("distance_km", "top_speed_kmh", "sprints", "high_speed_m")
    }
    tracking = {
        "matches": len(tracking_parts),
        "outfield_distance_km": float(np.mean(pooled["distance_km"])),
        "top_speed_kmh_median": float(np.median(pooled["top_speed_kmh"])),
        "sprints_per_player": float(np.mean(pooled["sprints"])),
        "high_speed_distance_m": float(np.mean(pooled["high_speed_m"])),
        "speed_band_shares": np.mean([m["speed_band_shares"] for m in tracking_parts], axis=0)
        .round(5)
        .tolist(),
        "ball_in_play_share": float(np.mean([m["ball_in_play_share"] for m in tracking_parts])),
        "ball_speed_kmh": {
            k: float(np.mean([m["ball_speed_kmh"][k] for m in tracking_parts]))
            for k in tracking_parts[0]["ball_speed_kmh"]
        },
        "team_length_m": float(np.median([m["team_length_m"] for m in tracking_parts])),
        "team_width_m": float(np.median([m["team_width_m"] for m in tracking_parts])),
    }
    return {"events": events, "tracking": tracking}
