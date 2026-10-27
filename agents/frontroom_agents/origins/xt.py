"""Expected threat (xT): how likely a team is to score from each part of the pitch within its next few
actions, if it plays the way a typical team plays from there.

Fitted on real Premier League 2017/18 events from the Wyscout public dataset (CC BY 4.0), following
Karun Singh's value-iteration formulation. Because xT(s) is the value of *typical* play from s, the change an
action makes, xT(after) - xT(before), is its value compared with what a typical player would have done.

Every match is resampled to give a bootstrap of the grid, so each credited action comes with an interval.

    python -m frontroom_agents.origins.xt ../data/raw/wyscout/events/events_England.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

COLS, ROWS = 16, 12
CELLS = COLS * ROWS
PITCH_LENGTH, PITCH_WIDTH = 105.0, 68.0
MODEL_PATH = Path(__file__).with_name("xt-wyscout-pl-2017.json")

SOURCE = "Wyscout public dataset, Premier League 2017/18 (CC BY 4.0), doi:10.6084/m9.figshare.c.4415000"

ACCURATE = 1801
GOAL = 101


def _cell_from_wyscout(x: float, y: float) -> int:
    """Wyscout gives 0-100 on both axes, attacking left to right, y = 0 on the attacking team's left."""
    col = min(int(x / 100 * COLS), COLS - 1)
    row = min(int(y / 100 * ROWS), ROWS - 1)
    return row * COLS + col


@dataclass
class _Counts:
    shots: np.ndarray
    goals: np.ndarray
    moves: np.ndarray
    transitions: np.ndarray  # successful moves, from-cell x to-cell

    @classmethod
    def zero(cls) -> _Counts:
        return cls(np.zeros(CELLS), np.zeros(CELLS), np.zeros(CELLS), np.zeros((CELLS, CELLS)))

    def add(self, other: _Counts, weight: float = 1.0) -> None:
        self.shots += weight * other.shots
        self.goals += weight * other.goals
        self.moves += weight * other.moves
        self.transitions += weight * other.transitions


def count_matches(events: list[dict]) -> dict[int, _Counts]:
    """Open-play shots and moves (passes and carries) per match, by grid cell."""
    by_match: dict[int, _Counts] = defaultdict(_Counts.zero)
    for event in events:
        positions = event["positions"]
        tags = {t["id"] for t in event["tags"]}
        counts = by_match[event["matchId"]]
        start = _cell_from_wyscout(positions[0]["x"], positions[0]["y"])
        if event["eventName"] == "Shot":
            counts.shots[start] += 1
            counts.goals[start] += GOAL in tags
        elif (event["eventName"] == "Pass" or event["subEventName"] == "Acceleration") and len(positions) > 1:
            counts.moves[start] += 1
            if ACCURATE in tags or event["subEventName"] == "Acceleration":
                end = _cell_from_wyscout(positions[1]["x"], positions[1]["y"])
                counts.transitions[start, end] += 1
    return by_match


def solve(counts: _Counts, iterations: int = 40) -> np.ndarray:
    """xT = P(shoot)·P(goal | shot) + P(move)·Σ P(move to z, kept)·xT(z), iterated to a fixed point."""
    actions = counts.shots + counts.moves
    with np.errstate(divide="ignore", invalid="ignore"):
        shoot = np.nan_to_num(counts.shots / actions)
        move = np.nan_to_num(counts.moves / actions)
        score = np.nan_to_num(counts.goals / counts.shots)
        transition = np.nan_to_num(counts.transitions / counts.moves[:, None])
    xt = np.zeros(CELLS)
    for _ in range(iterations):
        xt = shoot * score + move * (transition @ xt)
    return xt


def fit(events: list[dict], bootstrap: int = 40, seed: int = 7) -> dict:
    per_match = list(count_matches(events).values())
    total = _Counts.zero()
    for counts in per_match:
        total.add(counts)
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(bootstrap):
        resampled = _Counts.zero()
        for index, times in enumerate(np.bincount(rng.integers(0, len(per_match), len(per_match)))):
            if times:
                resampled.add(per_match[index], float(times))
        samples.append(solve(resampled))
    return {
        "source": SOURCE,
        "grid": {"cols": COLS, "rows": ROWS, "row0": "attacking team's left touchline"},
        "matches": len(per_match),
        "xt": np.round(solve(total), 5).tolist(),
        "bootstrap": [np.round(s, 5).tolist() for s in samples],
    }


class ExpectedThreat:
    """The fitted grid, read in pitch metres: x from own goal (0) to the opponent's (105), y across (0-68)."""

    def __init__(self, path: Path = MODEL_PATH):
        model = json.loads(path.read_text())
        self.xt = np.array(model["xt"])
        self.samples = np.array(model["bootstrap"])

    @staticmethod
    def cell(x: float, y: float) -> int:
        """Pitch metres, attacking towards x = 105. y = 68 is the attacking team's left."""
        col = min(max(int(x / PITCH_LENGTH * COLS), 0), COLS - 1)
        row = min(max(int((PITCH_WIDTH - y) / PITCH_WIDTH * ROWS), 0), ROWS - 1)
        return row * COLS + col

    def at(self, x: float, y: float) -> float:
        return float(self.xt[self.cell(x, y)])

    def samples_at(self, x: float, y: float) -> np.ndarray:
        return self.samples[:, self.cell(x, y)]


if __name__ == "__main__":
    events = json.loads(Path(sys.argv[1]).read_text())
    model = fit(events)
    MODEL_PATH.write_text(json.dumps(model, separators=(",", ":")))
    grid = np.array(model["xt"]).reshape(ROWS, COLS)
    print(f"fitted on {model['matches']} matches; xT ranges {grid.min():.4f} to {grid.max():.4f}")
