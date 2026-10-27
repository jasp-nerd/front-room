"""Physical reference statistics from the DFL/IDSSE 25 Hz tracking files.

The position files are several hundred MB of XML with one `<Frame>` per line, so they are
scanned line by line with a regular expression instead of being parsed into a tree.
DFL coordinates are centred on the pitch; only differences are used here, so no shift is needed.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from frontroom_engine.calibration.definitions import (
    FULL_MATCH_MINUTES,
    HIGH_SPEED_KMH,
    count_sprints,
    quantiles,
    speed_band_shares,
)

FRAME_RATE = 25.0
SHAPE_SAMPLE_EVERY = 25

_FRAMESET = re.compile(rb'<FrameSet GameSection="(\w+)" MatchId="[^"]*" TeamId="([^"]+)" PersonId="([^"]+)"')
_FRAME = re.compile(
    rb'<Frame N="(\d+)" T="[^"]*" X="([-\d.]+)" Y="([-\d.]+)"(?: Z="[-\d.]+")? D="[^"]*" S="([-\d.]+)"'
    rb'(?:.*?BallStatus="(\d)")?'
)
_GOALKEEPER = re.compile(r'<Player PersonId="([^"]+)"[^>]*PlayingPosition="TW"')


@dataclass
class _Track:
    frames: list[int] = field(default_factory=list)
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    speed_kmh: list[float] = field(default_factory=list)
    alive: list[bool] = field(default_factory=list)


def _read_tracks(positions_path: Path) -> dict[tuple[str, str, str], _Track]:
    tracks: dict[tuple[str, str, str], _Track] = {}
    current: _Track | None = None
    with positions_path.open("rb") as handle:
        for line in handle:
            frame = _FRAME.search(line)
            if frame and current is not None:
                current.frames.append(int(frame[1]))
                current.x.append(float(frame[2]))
                current.y.append(float(frame[3]))
                current.speed_kmh.append(float(frame[4]))
                current.alive.append(frame[5] == b"1")
                continue
            header = _FRAMESET.search(line)
            if header:
                key = (header[1].decode(), header[2].decode(), header[3].decode())
                current = tracks.setdefault(key, _Track())
    return tracks


def _team_shape(
    tracks: dict[tuple[str, str, str], _Track], goalkeepers: set[str]
) -> tuple[list[float], list[float]]:
    """Outfield length and width, sampled once a second while the ball is in play."""
    lengths: list[float] = []
    widths: list[float] = []
    sections = {section for section, team, _ in tracks if team == "BALL"}
    for section in sections:
        ball = next(t for (s, team, _), t in tracks.items() if s == section and team == "BALL")
        first = ball.frames[0]
        sampled = np.array(ball.frames)[np.array(ball.alive)][::SHAPE_SAMPLE_EVERY] - first
        teams: dict[str, list[_Track]] = defaultdict(list)
        for (s, team, person), track in tracks.items():
            if s == section and team not in ("BALL", "referee") and person not in goalkeepers:
                teams[team].append(track)
        n = ball.frames[-1] - first + 1
        for players in teams.values():
            xs = np.full((len(players), n), np.nan)
            ys = np.full((len(players), n), np.nan)
            for row, track in enumerate(players):
                index = np.array(track.frames) - first
                keep = (index >= 0) & (index < n)
                xs[row, index[keep]] = np.array(track.x)[keep]
                ys[row, index[keep]] = np.array(track.y)[keep]
            x_at, y_at = xs[:, sampled], ys[:, sampled]
            complete = np.sum(~np.isnan(x_at), axis=0) >= 9
            lengths.extend((np.nanmax(x_at, 0) - np.nanmin(x_at, 0))[complete])
            widths.extend((np.nanmax(y_at, 0) - np.nanmin(y_at, 0))[complete])
    return lengths, widths


def idsse_match_stats(positions_path: Path, information_path: Path) -> dict[str, Any]:
    """Per-match physical statistics for one IDSSE match."""
    goalkeepers = set(_GOALKEEPER.findall(information_path.read_text(encoding="utf-8")))
    tracks = _read_tracks(positions_path)
    per_person: dict[str, list[np.ndarray]] = defaultdict(list)
    for (_, team, person), track in tracks.items():
        if team not in ("BALL", "referee") and person not in goalkeepers:
            per_person[person].append(np.array(track.speed_kmh))
    full_match = [
        parts for parts in per_person.values() if sum(map(len, parts)) / FRAME_RATE / 60 > FULL_MATCH_MINUTES
    ]
    balls = [t for (_, team, _), t in tracks.items() if team == "BALL"]
    alive = np.concatenate([np.array(b.alive) for b in balls])
    ball_speed = np.concatenate([np.array(b.speed_kmh)[np.array(b.alive)] for b in balls])
    lengths, widths = _team_shape(tracks, goalkeepers)
    all_speeds = np.concatenate([np.concatenate(parts) for parts in full_match])
    return {
        "distance_km": [float(np.sum(np.concatenate(p)) / 3.6 / FRAME_RATE / 1000) for p in full_match],
        "top_speed_kmh": [float(np.max(np.concatenate(p))) for p in full_match],
        "sprints": [sum(count_sprints(s, FRAME_RATE) for s in p) for p in full_match],
        "high_speed_m": [
            float(np.sum(np.concatenate(p)[np.concatenate(p) >= HIGH_SPEED_KMH]) / 3.6 / FRAME_RATE)
            for p in full_match
        ],
        "speed_band_shares": speed_band_shares(all_speeds),
        "ball_in_play_share": float(alive.mean()),
        "ball_speed_kmh": quantiles(ball_speed),
        "team_length_m": float(np.median(lengths)),
        "team_width_m": float(np.median(widths)),
    }


def idsse_reference(raw_dir: Path) -> dict[str, Any]:
    """Pool the per-match statistics over every IDSSE match found in `raw_dir`."""
    matches = []
    for positions in sorted(raw_dir.glob("DFL_04_03_positions_raw_observed_*.xml")):
        suffix = positions.name.removeprefix("DFL_04_03_positions_raw_observed_")
        matches.append(idsse_match_stats(positions, raw_dir / f"DFL_02_01_matchinformation_{suffix}"))
    pooled = {
        key: [v for m in matches for v in m[key]]
        for key in ("distance_km", "top_speed_kmh", "sprints", "high_speed_m")
    }
    return {
        "source": "DFL/IDSSE open tracking, 7 German matches 2022/23 (CC BY 4.0)",
        "matches": len(matches),
        "outfield_distance_km": float(np.mean(pooled["distance_km"])),
        "top_speed_kmh_median": float(np.median(pooled["top_speed_kmh"])),
        "sprints_per_player": float(np.mean(pooled["sprints"])),
        "high_speed_distance_m": float(np.mean(pooled["high_speed_m"])),
        "speed_band_shares": np.mean([m["speed_band_shares"] for m in matches], axis=0).round(5).tolist(),
        "ball_in_play_share": float(np.mean([m["ball_in_play_share"] for m in matches])),
        "ball_speed_kmh": {
            k: float(np.mean([m["ball_speed_kmh"][k] for m in matches])) for k in matches[0]["ball_speed_kmh"]
        },
        "team_length_m": float(np.median([m["team_length_m"] for m in matches])),
        "team_width_m": float(np.median([m["team_width_m"] for m in matches])),
    }
