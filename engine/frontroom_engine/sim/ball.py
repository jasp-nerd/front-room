"""Ball physics: quadratic air drag in flight, bounces, and rolling resistance on the grass.

The same integrator moves the ball during play and predicts its path for decisions and
interception targeting, so what a player anticipates and what then happens never disagree.
Launch speeds are solved against that integrator (closed form on the ground, a lookup table
in the air) rather than taken from a separate kinematic shortcut.
"""

import numpy as np

TICK = 0.1
SUBSTEPS = 5
GRAVITY = 9.81
AIR_DRAG = 0.010
ROLL_DECEL = 0.6
ROLL_DAMPING = 0.12
RESTITUTION = 0.55
BOUNCE_GRIP = 0.65
MIN_BOUNCE_SPEED = 1.0
MAX_PASS_SPEED = 26.0


def integrate(
    pos: np.ndarray, vel: np.ndarray, steps: int, dt: float = TICK
) -> tuple[np.ndarray, np.ndarray]:
    """Advance n balls for `steps` intervals of `dt`; returns positions and velocities, each (steps, n, 3)."""
    p = np.array(pos, dtype=float, ndmin=2)
    v = np.array(vel, dtype=float, ndmin=2)
    h = dt / SUBSTEPS
    positions = np.empty((steps, *p.shape))
    velocities = np.empty((steps, *v.shape))
    for step in range(steps):
        for _ in range(SUBSTEPS):
            airborne = (p[:, 2] > 1e-3) | (v[:, 2] > 1e-3)
            speed = np.linalg.norm(v, axis=1, keepdims=True)
            air_acc = -AIR_DRAG * speed * v
            air_acc[:, 2] -= GRAVITY
            ground_speed = np.hypot(v[:, 0], v[:, 1])
            slowed = np.maximum(0.0, ground_speed - (ROLL_DECEL + ROLL_DAMPING * ground_speed) * h)
            roll_scale = np.divide(slowed, ground_speed, out=np.zeros_like(slowed), where=ground_speed > 1e-9)
            v = np.where(
                airborne[:, None],
                v + air_acc * h,
                v * np.stack([roll_scale, roll_scale, np.zeros_like(slowed)], 1),
            )
            p = p + v * h
            landed = p[:, 2] < 0.0
            if np.any(landed):
                p[landed, 2] = 0.0
                bounce = -RESTITUTION * v[landed, 2]
                v[landed, 2] = np.where(bounce > MIN_BOUNCE_SPEED, bounce, 0.0)
                v[landed, :2] *= BOUNCE_GRIP
        positions[step] = p
        velocities[step] = v
    return positions, velocities


def ground_launch_speed(distance: np.ndarray, arrival_speed: np.ndarray) -> np.ndarray:
    """Initial speed for a rolling ball to cover `distance` and still be moving at `arrival_speed`.

    Solves D = (v0 - va)/c1 - (c0/c1^2) ln((c0 + c1 v0)/(c0 + c1 va)) by Newton's method.
    """
    c0, c1 = ROLL_DECEL, ROLL_DAMPING
    d = np.asarray(distance, dtype=float)
    va = np.asarray(arrival_speed, dtype=float)
    v0 = np.sqrt(va**2 + 2 * c0 * d) + 0.1 * d * c1
    for _ in range(8):
        covered = (v0 - va) / c1 - (c0 / c1**2) * np.log((c0 + c1 * v0) / (c0 + c1 * va))
        v0 = v0 - (covered - d) * (c0 + c1 * v0) / v0
    return np.clip(v0, va, MAX_PASS_SPEED)


def ground_flight_time(launch_speed: np.ndarray, arrival_speed: np.ndarray) -> np.ndarray:
    c0, c1 = ROLL_DECEL, ROLL_DAMPING
    return np.log((launch_speed + c0 / c1) / (np.asarray(arrival_speed) + c0 / c1)) / c1


def _build_loft_table() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    angles = np.radians(np.arange(10.0, 61.0, 5.0))
    speeds = np.arange(5.0, 36.0, 0.5)
    grid_angle, grid_speed = np.meshgrid(angles, speeds, indexing="ij")
    flat_angle, flat_speed = grid_angle.ravel(), grid_speed.ravel()
    vel = np.stack(
        [flat_speed * np.cos(flat_angle), np.zeros_like(flat_speed), flat_speed * np.sin(flat_angle)], 1
    )
    dt = 0.02
    launch_height = np.tile([0.0, 0.0, 0.11], (vel.shape[0], 1))
    positions, velocities = integrate(launch_height, vel, 500, dt=dt)
    vertical = velocities[:, :, 2]
    bounced = np.vstack([np.zeros((1, vel.shape[0]), bool), (vertical[1:] >= 0) & (vertical[:-1] < 0)])
    first_landing = np.where(bounced.any(axis=0), np.argmax(bounced, axis=0), len(positions) - 1)
    ranges = positions[first_landing, np.arange(vel.shape[0]), 0].reshape(grid_angle.shape)
    times = ((first_landing + 1) * dt).reshape(grid_angle.shape)
    return angles, speeds, ranges, times


_LOFT_ANGLES, _LOFT_SPEEDS, _LOFT_RANGES, _LOFT_TIMES = _build_loft_table()


def lofted_launch(distance: float, angle_deg: float) -> tuple[float, float]:
    """Launch speed and flight time for a lofted ball to first land `distance` metres away."""
    row = int(np.argmin(np.abs(_LOFT_ANGLES - np.radians(angle_deg))))
    ranges = _LOFT_RANGES[row]
    speed = float(np.interp(distance, ranges, _LOFT_SPEEDS))
    time = float(np.interp(distance, ranges, _LOFT_TIMES[row]))
    return speed, time


def velocity_towards(
    start: np.ndarray, target: np.ndarray, speed: float, angle_deg: float = 0.0
) -> np.ndarray:
    """3-D launch velocity from `start` towards the 2-D `target` at `speed`, elevated by `angle_deg`."""
    direction = np.asarray(target[:2], dtype=float) - np.asarray(start[:2], dtype=float)
    direction /= max(np.linalg.norm(direction), 1e-9)
    elevation = np.radians(angle_deg)
    horizontal = speed * np.cos(elevation)
    return np.array([direction[0] * horizontal, direction[1] * horizontal, speed * np.sin(elevation)])


def rotate(vector: np.ndarray, angle: float) -> np.ndarray:
    """Rotate the horizontal part of a 3-D velocity by `angle` radians."""
    c, s = np.cos(angle), np.sin(angle)
    x, y = vector[0], vector[1]
    return np.array([c * x - s * y, s * x + c * y, vector[2]])
