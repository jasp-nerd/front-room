"""Statistic definitions shared by the reference builders and the simulated-match metrics.

Keeping the bands and thresholds in one place is what makes the scorecard a like-for-like
comparison: the real and synthetic numbers are computed with the same cut points.
"""

from collections.abc import Sequence

import numpy as np

PASS_LENGTH_BANDS: tuple[tuple[str, float, float], ...] = (
    ("0-10", 0.0, 10.0),
    ("10-20", 10.0, 20.0),
    ("20-30", 20.0, 30.0),
    ("30-40", 30.0, 40.0),
    ("40-60", 40.0, 60.0),
    ("60+", 60.0, float("inf")),
)

SPEED_BANDS_KMH: tuple[float, ...] = (7.0, 14.4, 19.8, 25.2)
SPRINT_KMH = 25.2
HIGH_SPEED_KMH = 19.8
SPRINT_MIN_SECONDS = 1.0
FULL_MATCH_MINUTES = 85.0

QUANTILES = (10, 25, 50, 75, 90)


def quantiles(values: Sequence[float] | np.ndarray, levels: Sequence[int] = QUANTILES) -> dict[str, float]:
    """Percentiles keyed as 'p10', 'p50', ... so JSON reports read naturally."""
    array = np.asarray(values, dtype=float)
    return {f"p{level}": round(float(np.percentile(array, level)), 3) for level in levels}


def pass_band(length_m: float) -> str:
    for name, low, high in PASS_LENGTH_BANDS:
        if low <= length_m < high:
            return name
    raise ValueError(f"negative pass length {length_m}")


def speed_band_shares(speeds_kmh: np.ndarray) -> list[float]:
    """Share of samples in each speed band (<7, 7-14.4, 14.4-19.8, 19.8-25.2, >25.2 km/h)."""
    counts = np.bincount(np.digitize(speeds_kmh, SPEED_BANDS_KMH), minlength=len(SPEED_BANDS_KMH) + 1)
    return [round(float(c), 5) for c in counts / max(1, counts.sum())]


def count_sprints(speeds_kmh: np.ndarray, frame_rate: float) -> int:
    """Number of runs that stay above sprint speed for at least one second."""
    fast = np.concatenate([[False], speeds_kmh >= SPRINT_KMH, [False]])
    edges = np.flatnonzero(np.diff(fast.astype(np.int8)))
    run_lengths = edges[1::2] - edges[0::2]
    return int(np.sum(run_lengths >= SPRINT_MIN_SECONDS * frame_rate))
