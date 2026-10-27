"""Write a simulated match to disk: metadata.json, events.jsonl, tracking.parquet, truth.json.

Tracking is stored one row per 25 Hz frame with list columns for the players on the pitch, so
a row maps one-to-one onto a `tracking-frame` record (`tracking_frame` does that conversion).
"""

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from frontroom_engine import __version__
from frontroom_engine.calibration.reference import ATTRIBUTION
from frontroom_engine.extract.events import Feed, extract_events
from frontroom_engine.extract.tracking import FRAME_RATE, Tracking, resample
from frontroom_engine.extract.truth import build_truth, story_action_ids
from frontroom_engine.league.model import Player
from frontroom_engine.pitch import PITCH_LENGTH, PITCH_WIDTH
from frontroom_engine.sim.match import MatchResult
from frontroom_engine.sim.setup import TeamSetup


@dataclass(frozen=True)
class MatchFiles:
    metadata: Path
    events: Path
    tracking: Path
    truth: Path


def tracking_table(tracking: Tracking) -> pa.Table:
    present = tracking.roster >= 0
    offsets = np.concatenate([[0], np.cumsum(present.sum(axis=1))]).astype(np.int32)
    slots = np.nonzero(present)[1]
    ids = pa.DictionaryArray.from_arrays(
        pa.array(tracking.roster[present], pa.int16()), pa.array(tracking.player_ids)
    )
    sides = pa.DictionaryArray.from_arrays(
        pa.array((slots >= 11).astype(np.int8)), pa.array(["home", "away"])
    )

    def listed(values: pa.Array) -> pa.ListArray:
        return pa.ListArray.from_arrays(pa.array(offsets), values)

    return pa.table(
        {
            "frame": pa.array(tracking.frame, pa.int32()),
            "period": pa.array(tracking.period, pa.int8()),
            "clock_ms": pa.array(tracking.clock_ms, pa.int32()),
            "ball_x": pa.array(np.round(tracking.ball[:, 0], 2), pa.float32()),
            "ball_y": pa.array(np.round(tracking.ball[:, 1], 2), pa.float32()),
            "ball_z": pa.array(np.round(np.maximum(tracking.ball[:, 2], 0.0), 2), pa.float32()),
            "ball_alive": pa.array(tracking.alive),
            "player_id": listed(ids),
            "side": listed(sides),
            "x": listed(pa.array(np.round(tracking.pos[present][:, 0], 2), pa.float32())),
            "y": listed(pa.array(np.round(tracking.pos[present][:, 1], 2), pa.float32())),
            "speed": listed(pa.array(np.round(tracking.speed[present], 2), pa.float32())),
        }
    )


def _cm(value: float) -> float:
    """Undo float32 noise (5.289999961853027 -> 5.29); positions are stored to the centimetre."""
    return round(float(value), 2)


def tracking_frame(row: Mapping[str, Any], match_id: str) -> dict[str, Any]:
    """One Parquet row as a `tracking-frame` record."""
    return {
        "matchId": match_id,
        "frame": int(row["frame"]),
        "period": int(row["period"]),
        "clockMs": int(row["clock_ms"]),
        "ball": {"x": _cm(row["ball_x"]), "y": _cm(row["ball_y"]), "z": _cm(row["ball_z"])},
        "players": [
            {"playerId": pid, "side": side, "x": _cm(x), "y": _cm(y), "speed": _cm(v)}
            for pid, side, x, y, v in zip(
                row["player_id"], row["side"], row["x"], row["y"], row["speed"], strict=True
            )
        ],
    }


def read_tracking_frames(path: Path, match_id: str, limit: int | None = None) -> Iterator[dict[str, Any]]:
    table = pq.read_table(path)
    rows = table.slice(0, limit) if limit is not None else table
    for row in rows.to_pylist():
        yield tracking_frame(row, match_id)


def read_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _squad_entry(player: Player, starting: bool) -> dict[str, Any]:
    return {
        "playerId": player.id,
        "name": f"{player.first_name} {player.last_name}",
        "shortName": player.display_name,
        "number": player.number,
        "role": player.role.value,
        "starting": starting,
    }


def _team(team: TeamSetup) -> dict[str, Any]:
    club = team.club
    return {
        "clubId": club.id,
        "name": club.name,
        "short": club.short,
        "colours": [club.primary_colour, club.secondary_colour],
        "formation": team.style.formation,
        "squad": [_squad_entry(p, True) for p in club.starting_eleven()]
        + [_squad_entry(p, False) for p in club.bench()],
    }


def build_metadata(result: MatchResult, feed: Feed, tracking: Tracking) -> dict[str, Any]:
    setup = result.setup
    periods = []
    for period in (1, 2):
        frames = np.flatnonzero(tracking.period == period)
        periods.append(
            {
                "period": period,
                "firstFrame": int(frames[0]),
                "frames": len(frames),
                "durationMs": int(tracking.clock_ms[frames[-1]]),
            }
        )
    home_goals, away_goals = result.state.score
    return {
        "matchId": setup.match_id,
        "competition": f"{setup.league.name} {setup.league.season}",
        "seed": setup.seed,
        "leagueSeed": setup.league.seed,
        "engine": {
            "name": "frontroom-engine",
            "version": __version__,
            "generator": "G_B physical simulation",
        },
        "pitch": {"length": PITCH_LENGTH, "width": PITCH_WIDTH},
        "home": _team(setup.home),
        "away": _team(setup.away),
        "score": {"home": home_goals, "away": away_goals},
        "periods": periods,
        "trackingRateHz": FRAME_RATE,
        "events": len(feed.events),
        "steered": bool(result.branches),
        "attribution": ATTRIBUTION,
    }


def write_match(
    result: MatchResult,
    out_dir: Path,
    steering: Mapping[str, Any] | None = None,
    *,
    with_tracking: bool = True,
) -> MatchFiles:
    """Extract the feed and tracking from `result` and write the match files into `out_dir`.

    `with_tracking=False` skips the 15 MB Parquet file for bulk runs that only need events and truth.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    keep = frozenset(i for beat in result.state.beats for i in story_action_ids(beat.detail))
    feed = extract_events(result.setup.match_id, result.setup.seed, result.state.actions, keep)
    tracking = resample(result.recording)
    files = MatchFiles(
        out_dir / "metadata.json",
        out_dir / "events.jsonl",
        out_dir / "tracking.parquet",
        out_dir / "truth.json",
    )
    files.metadata.write_text(json.dumps(build_metadata(result, feed, tracking), indent=2) + "\n")
    files.events.write_text("".join(json.dumps(event, separators=(",", ":")) + "\n" for event in feed.events))
    if with_tracking:
        pq.write_table(tracking_table(tracking), files.tracking, compression="zstd")
    files.truth.write_text(json.dumps(build_truth(result, feed, steering), separators=(",", ":")) + "\n")
    return files
