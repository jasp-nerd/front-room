"""Attacking-frame transforms and the hand-built pitch value potential.

Decisions are easiest to reason about with the team attacking towards x = 105. The transform
is a 180-degree rotation, so left and right flanks stay consistent for both teams.
"""

import numpy as np

from frontroom_engine.pitch import CENTRE_Y, GOAL_LEFT_POST, GOAL_RIGHT_POST, PITCH_LENGTH, PITCH_WIDTH


def attack_sign(team: int, period: int) -> int:
    """+1 when `team` attacks towards x = 105. The home side does so in the first half."""
    return 1 if (team == 0) == (period == 1) else -1


def to_attack_frame(points: np.ndarray, sign: int) -> np.ndarray:
    """Rotate absolute coordinates into the frame where the team attacks towards x = 105.

    The transform is its own inverse, so it also maps attacking-frame points back.
    """
    if sign > 0:
        return np.asarray(points, dtype=float)
    return np.array([PITCH_LENGTH, PITCH_WIDTH]) - np.asarray(points, dtype=float)


def goal_angle(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Angle (radians) subtended by the goal mouth at the attacked goal, attacking frame."""
    to_left = np.arctan2(GOAL_LEFT_POST - y, PITCH_LENGTH - x)
    to_right = np.arctan2(GOAL_RIGHT_POST - y, PITCH_LENGTH - x)
    return np.abs(to_right - to_left)


def goal_distance(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.hypot(PITCH_LENGTH - np.asarray(x), CENTRE_Y - np.asarray(y))


def threat(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Value of having the ball at (x, y), attacking frame, on a rough 0..1 scale.

    A hand-built potential: closeness to goal weighted by the visible goal angle, plus a
    territorial term. It is deliberately not fitted to any event data (no xT, no VAEP), so the
    decision model stays independent of the analytics that are later run on the output.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    angle = goal_angle(x, y) / goal_angle(np.array(PITCH_LENGTH - 6.0), np.array(CENTRE_Y))
    chance = 0.55 * np.exp(-goal_distance(x, y) / 16.0) * np.clip(angle, 0.0, 1.0) ** 0.4
    territory = 0.25 * (np.clip(x, 0.0, PITCH_LENGTH) / PITCH_LENGTH) ** 2
    return 0.05 + chance + territory


def inside_pitch(points: np.ndarray, margin: float = 0.0) -> np.ndarray:
    p = np.atleast_2d(points)
    return (
        (p[:, 0] >= margin)
        & (p[:, 0] <= PITCH_LENGTH - margin)
        & (p[:, 1] >= margin)
        & (p[:, 1] <= PITCH_WIDTH - margin)
    )
