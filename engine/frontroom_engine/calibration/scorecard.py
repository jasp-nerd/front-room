"""Realism scorecard: N simulated matches against the cached open-data reference.

Tolerances are fixed in `CHECKS` and were written down before the scorecard was first run.
They are not loosened to make a check pass; a failing check is reported as a failure.
Relative tolerances suit counts and distances; absolute ones suit shares and rates.
"""

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import cache
from typing import Any, Literal

import numpy as np

from frontroom_engine.calibration.metrics import event_metrics, summarise, tracking_metrics
from frontroom_engine.calibration.reference import load_reference
from frontroom_engine.extract.events import extract_events
from frontroom_engine.extract.tracking import resample
from frontroom_engine.league import DEFAULT_LEAGUE_SEED, League, build_league
from frontroom_engine.sim.match import simulate_match

Path = tuple[str | int, ...]


@dataclass(frozen=True)
class Check:
    name: str
    path: Path
    kind: Literal["relative", "absolute"]
    tolerance: float


def _bands() -> tuple[Check, ...]:
    names = ("0-10", "10-20", "20-30", "30-40", "40-60", "60+")
    return tuple(
        Check(f"Pass accuracy {n} m", ("events", "pass_accuracy_by_length", n), "absolute", 0.08)
        for n in names
    )


def _speed_bands() -> tuple[Check, ...]:
    labels = ("<7", "7-14.4", "14.4-19.8", "19.8-25.2", ">25.2")
    return tuple(
        Check(
            f"Time share {label} km/h",
            ("tracking", "speed_band_shares", i),
            "relative",
            0.15 if i < 2 else 0.30,
        )
        for i, label in enumerate(labels)
    )


CHECKS: tuple[Check, ...] = (
    Check("On-ball actions per match", ("events", "actions_per_match"), "relative", 0.20),
    Check("Passes per match", ("events", "passes_per_match"), "relative", 0.15),
    Check("Pass accuracy", ("events", "pass_accuracy"), "absolute", 0.04),
    *_bands(),
    Check("Pass length median (m)", ("events", "pass_length_m", "p50"), "relative", 0.15),
    Check("Pass length p90 (m)", ("events", "pass_length_m", "p90"), "relative", 0.15),
    Check("Shots per match", ("events", "shots_per_match"), "relative", 0.20),
    Check("Shot conversion", ("events", "shot_conversion"), "absolute", 0.03),
    Check("Shot distance median (m)", ("events", "shot_distance_m", "p50"), "relative", 0.15),
    Check("Goals per match", ("events", "goals_per_match"), "relative", 0.20),
    Check("Home win share", ("events", "results", "home"), "absolute", 0.10),
    Check("Draw share", ("events", "results", "draw"), "absolute", 0.10),
    Check("Away win share", ("events", "results", "away"), "absolute", 0.10),
    Check("Inter-event gap median (s)", ("events", "inter_event_gap_s", "p50"), "relative", 0.20),
    Check("Inter-event gap p90 (s)", ("events", "inter_event_gap_s", "p90"), "relative", 0.25),
    Check("Fouls per match", ("events", "fouls_per_match"), "relative", 0.20),
    Check("Yellow cards per match", ("events", "yellow_cards_per_match"), "relative", 0.30),
    Check("Corners per match", ("events", "corners_per_match"), "relative", 0.25),
    Check("Throw-ins per match", ("events", "throw_ins_per_match"), "relative", 0.20),
    Check("Offsides per match", ("events", "offsides_per_match"), "relative", 0.40),
    Check("Distance per outfield player (km)", ("tracking", "outfield_distance_km"), "relative", 0.10),
    Check("Top speed median (km/h)", ("tracking", "top_speed_kmh_median"), "relative", 0.08),
    *_speed_bands(),
    Check("Sprints per player", ("tracking", "sprints_per_player"), "relative", 0.30),
    Check("High-speed distance per player (m)", ("tracking", "high_speed_distance_m"), "relative", 0.25),
    Check("Team length (m)", ("tracking", "team_length_m"), "relative", 0.10),
    Check("Team width (m)", ("tracking", "team_width_m"), "relative", 0.10),
    Check("Ball-in-play share", ("tracking", "ball_in_play_share"), "absolute", 0.05),
    Check("Ball speed median (km/h)", ("tracking", "ball_speed_kmh", "p50"), "relative", 0.20),
    Check("Ball speed p90 (km/h)", ("tracking", "ball_speed_kmh", "p90"), "relative", 0.15),
)


def fixture(league: League, index: int, seed: int) -> tuple[str, str]:
    """A deterministic pairing of two different clubs for match `index` of a scorecard run."""
    rng = np.random.default_rng([seed, index])
    home, away = rng.choice(len(league.clubs), size=2, replace=False)
    return league.clubs[int(home)].short, league.clubs[int(away)].short


@cache
def _league() -> League:
    return build_league(DEFAULT_LEAGUE_SEED)


def _simulate(args: tuple[int, int]) -> tuple[dict[str, Any], dict[str, Any]]:
    index, seed = args
    league = _league()
    home, away = fixture(league, index, seed)
    result = simulate_match(league, home, away, seed * 1000 + index)
    feed = extract_events(result.setup.match_id, result.setup.seed, result.state.actions)
    return event_metrics(feed.events, (result.state.score[0], result.state.score[1])), tracking_metrics(
        resample(result.recording)
    )


def _lookup(tree: Any, path: Path) -> float:
    for key in path:
        tree = tree[key]
    return float(tree)


def evaluate(summary: dict[str, Any], reference: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for check in CHECKS:
        expected, observed = _lookup(reference, check.path), _lookup(summary, check.path)
        error = observed - expected
        relative = error / expected if expected else float("inf")
        deviation = abs(relative) if check.kind == "relative" else abs(error)
        rows.append(
            {
                "name": check.name,
                "reference": round(expected, 4),
                "simulated": round(observed, 4),
                "tolerance": f"±{check.tolerance:.0%}" if check.kind == "relative" else f"±{check.tolerance}",
                "deviation": round(deviation, 4),
                "pass": bool(deviation <= check.tolerance),
            }
        )
    return rows


def scorecard(matches: int, seed: int = 1, workers: int | None = None) -> dict[str, Any]:
    """Simulate `matches` matches in parallel and score them against the reference."""
    jobs = [(index, seed) for index in range(matches)]
    with ProcessPoolExecutor(max_workers=workers or os.cpu_count()) as pool:
        parts = list(pool.map(_simulate, jobs))
    summary = summarise([p[0] for p in parts], [p[1] for p in parts])
    rows = evaluate(summary, load_reference())
    return {
        "matches": matches,
        "seed": seed,
        "passed": sum(row["pass"] for row in rows),
        "total": len(rows),
        "checks": rows,
        "summary": summary,
    }


def markdown(report: dict[str, Any]) -> str:
    passed, total, matches = report["passed"], report["total"], report["matches"]
    lines = [
        f"# Realism scorecard: {passed}/{total} checks pass ({matches} matches)",
        "",
        "| Check | Reference | Simulated | Tolerance | Pass |",
        "|---|---:|---:|---:|:---:|",
    ]
    for row in report["checks"]:
        verdict = "yes" if row["pass"] else "no"
        values = f"{row['reference']:g} | {row['simulated']:g} | {row['tolerance']}"
        lines.append(f"| {row['name']} | {values} | {verdict} |")
    return "\n".join(lines) + "\n"
