"""Player kinematics and the time-to-reach model.

Players are point masses steering towards a target with capped acceleration, braking and top
speed. The same caps drive `time_to_reach`, which decisions and interception use, so a player
never commits to a ball he could not physically get to.
"""

import numpy as np

from frontroom_engine.sim.ball import TICK

BRAKING = 5.5
STEER_RESPONSE = 0.35
ARRIVAL_BRAKING = 3.0


def steer(
    pos: np.ndarray,
    vel: np.ndarray,
    target: np.ndarray,
    desired_speed: np.ndarray,
    top_speed: np.ndarray,
    acceleration: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """One tick of motion for every player; all arrays are per player."""
    offset = target - pos
    distance = np.linalg.norm(offset, axis=1)
    arrive_cap = np.sqrt(2.0 * ARRIVAL_BRAKING * distance)
    speed = np.minimum(np.minimum(desired_speed, arrive_cap), top_speed)
    direction = np.divide(
        offset, distance[:, None], out=np.zeros_like(offset), where=distance[:, None] > 1e-6
    )
    wanted = direction * speed[:, None]
    change = (wanted - vel) / STEER_RESPONSE
    speeding_up = np.einsum("ij,ij->i", change, vel) >= 0
    limit = np.where(speeding_up, acceleration, BRAKING)
    magnitude = np.linalg.norm(change, axis=1)
    change *= np.minimum(1.0, limit / np.maximum(magnitude, 1e-9))[:, None]
    new_vel = vel + change * TICK
    new_speed = np.linalg.norm(new_vel, axis=1)
    new_vel *= np.minimum(1.0, top_speed / np.maximum(new_speed, 1e-9))[:, None]
    return pos + new_vel * TICK, new_vel


def time_to_reach(
    pos: np.ndarray,
    vel: np.ndarray,
    points: np.ndarray,
    top_speed: np.ndarray,
    acceleration: np.ndarray,
    reaction: np.ndarray,
    reach: float = 0.0,
) -> np.ndarray:
    """Seconds for each player (rows) to get within `reach` metres of each point (columns).

    During the reaction time the player carries on with his current velocity; after that he
    runs at the point with capped acceleration, as in Spearman-style pitch-control models.
    """
    start = pos + vel * reaction[:, None]
    distance = np.maximum(np.linalg.norm(points[None, :, :] - start[:, None, :], axis=2) - reach, 0.0)
    v, a = top_speed[:, None], acceleration[:, None]
    ramp = v**2 / (2 * a)
    running = np.where(distance <= ramp, np.sqrt(2 * distance / a), (distance - ramp) / v + v / a)
    return reaction[:, None] + running
