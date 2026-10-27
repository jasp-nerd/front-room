"""Resample the 10 Hz simulation to 25 Hz tracking frames.

Positions and speeds are interpolated linearly between simulation ticks. When a slot changes
hands between two ticks (a substitution or a sending-off) the frame keeps the earlier tick's
values, so two different players are never blended into one trajectory.
"""

from dataclasses import dataclass

import numpy as np

from frontroom_engine.sim.recorder import Recording

FRAME_RATE = 25
SIM_RATE = 10


@dataclass(frozen=True)
class Tracking:
    frame: np.ndarray
    period: np.ndarray
    clock_ms: np.ndarray
    ball: np.ndarray
    pos: np.ndarray
    speed: np.ndarray
    roster: np.ndarray
    """Index into `player_ids` per frame and slot; -1 when the slot has nobody on the pitch."""
    alive: np.ndarray
    player_ids: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.frame)


def _period_frames(
    recording: Recording, period: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """For each 25 Hz frame of the period: the ticks either side, the blend weight and the clock."""
    ticks = np.flatnonzero(recording.period[: recording.length] == period)
    first, last = int(ticks[0]), int(ticks[-1])
    duration_ms = int(recording.clock_ms[last])
    clock = np.arange(0, duration_ms + 1, 1000 // FRAME_RATE)
    position = clock / (1000 / SIM_RATE)
    lower = np.minimum(first + np.floor(position).astype(int), last)
    upper = np.minimum(lower + 1, last)
    weight = position - np.floor(position)
    return lower, upper, weight, clock


def resample(recording: Recording) -> Tracking:
    parts: dict[str, list[np.ndarray]] = {
        k: [] for k in ("period", "clock", "ball", "pos", "speed", "roster", "alive")
    }
    for period in (1, 2):
        lower, upper, weight, clock = _period_frames(recording, period)
        same_player = recording.roster[lower] == recording.roster[upper]
        w = weight[:, None]
        slot_w = np.where(same_player, w, 0.0)
        parts["period"].append(np.full(len(clock), period, dtype=np.int8))
        parts["clock"].append(clock)
        parts["ball"].append((1 - w) * recording.ball[lower] + w * recording.ball[upper])
        parts["pos"].append(
            (1 - slot_w[..., None]) * recording.pos[lower] + slot_w[..., None] * recording.pos[upper]
        )
        parts["speed"].append((1 - slot_w) * recording.speed[lower] + slot_w * recording.speed[upper])
        parts["roster"].append(recording.roster[lower])
        parts["alive"].append(recording.alive[lower])
    period = np.concatenate(parts["period"])
    return Tracking(
        frame=np.arange(len(period)),
        period=period,
        clock_ms=np.concatenate(parts["clock"]),
        ball=np.concatenate(parts["ball"]).astype(np.float32),
        pos=np.concatenate(parts["pos"]).astype(np.float32),
        speed=np.concatenate(parts["speed"]).astype(np.float32),
        roster=np.concatenate(parts["roster"]),
        alive=np.concatenate(parts["alive"]),
        player_ids=tuple(recording.player_ids),
    )
