"""Physical shots, blocks and the goalkeeper.

One vectorised function resolves a batch of shot attempts. The real attempt runs it once with
noise from the tape; the latent xG runs it a few hundred times with fresh noise from the same
state. So the ground-truth chance is P(goal) under this simulator's physics, not a fitted model.
"""

from dataclasses import dataclass

import numpy as np

from frontroom_engine.pitch import CENTRE_Y, GOAL_HEIGHT, GOAL_WIDTH
from frontroom_engine.sim.ball import TICK, integrate

GOAL, SAVED, PARRIED, BLOCKED, OFF_TARGET = range(5)
OUTCOMES = ("goal", "saved", "parried", "blocked", "off_target")
MONTE_CARLO_SAMPLES = 256
BALL_RADIUS = 0.11
KEEPER_STANDING_REACH = 1.75
KEEPER_DIVE_SPEED = 5.0
KEEPER_MAX_REACH = 3.2
BLOCK_REACH = 1.5
BLOCK_CHANCE = 0.7
FLIGHT_STEPS = 30
CATCHABLE = 0.35
"""Shots this close to the keeper's body are held; anything further out is parried."""
PENALTY_GUESS = 1.6
"""A keeper facing a penalty must wait for the kick and often guesses wrong, so he reacts late."""
SAVE_SOFTNESS = 0.3
"""Width (m) of the zone at the edge of the keeper's reach where saves become uncertain."""
AIM_SIDE, AIM_HEIGHT, KEEPER_REACTION, KEEPER_HANDLING, FIRST_BLOCK = range(5)


def uniform_columns(blockers: int) -> int:
    """Uniform draws one shot attempt needs: aim, keeper reaction and handling, one per blocker."""
    return FIRST_BLOCK + blockers


@dataclass(frozen=True)
class ShotSituation:
    start: np.ndarray
    goal_x: float
    keeper_pos: np.ndarray
    keeper_reaction: float
    keeper_skill: float
    blockers: np.ndarray
    finishing: float
    pressure: float
    header: bool
    penalty: bool


@dataclass(frozen=True)
class ShotBatch:
    outcome: np.ndarray
    resolve_step: np.ndarray
    blocker: np.ndarray
    velocity: np.ndarray
    on_target: np.ndarray


def aim_spread(situation: ShotSituation) -> float:
    """Lateral standard deviation of the shot at the goal line, in metres."""
    distance = abs(situation.goal_x - situation.start[0])
    spread = situation.finishing * (0.5 + distance / 14.0) * (1.0 + 0.9 * situation.pressure)
    return spread * (1.6 if situation.header else 1.0) * (0.4 if situation.penalty else 1.0)


def _aims(
    situation: ShotSituation, normals: np.ndarray, uniforms: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    keeper_side = np.sign(situation.keeper_pos[1] - CENTRE_Y) or 1.0
    inset = (2.4 + 0.9 * uniforms[:, AIM_SIDE]) if situation.penalty else (1.8 + 1.5 * uniforms[:, AIM_SIDE])
    lateral = CENTRE_Y - keeper_side * inset
    height = 0.2 + (0.9 if situation.header else 1.5) * uniforms[:, AIM_HEIGHT]
    spread = aim_spread(situation)
    aim_y = lateral + spread * normals[:, 0]
    aim_z = np.maximum(0.0, height + 0.6 * spread * normals[:, 1])
    speed = (13.0 if situation.header else 25.0) * (1.0 - 0.1 * situation.pressure) + 1.5 * normals[:, 2]
    return np.stack([np.full_like(aim_y, situation.goal_x), aim_y, aim_z], axis=1), speed


def _line_crossing(path: np.ndarray, start: np.ndarray, step: np.ndarray, goal_x: float) -> np.ndarray:
    """Interpolate where each path crosses the goal line, between the samples either side of it."""
    rows = np.arange(path.shape[1])
    after = path[step, rows]
    before = np.where((step > 0)[:, None], path[np.maximum(step - 1, 0), rows], start)
    span = after[:, 0] - before[:, 0]
    fraction = np.clip(
        np.divide(goal_x - before[:, 0], span, out=np.ones_like(span), where=np.abs(span) > 1e-9), 0, 1
    )
    return before + fraction[:, None] * (after - before)


def resolve_shots(situation: ShotSituation, normals: np.ndarray, uniforms: np.ndarray) -> ShotBatch:
    """Resolve n attempts; `normals` is (n, 3) and `uniforms` is (n, uniform_columns(blockers))."""
    n = normals.shape[0]
    aims, speed = _aims(situation, normals, uniforms)
    start = np.broadcast_to(situation.start, (n, 3))
    offset = aims - start
    flight = np.linalg.norm(offset[:, :2], axis=1) / speed
    velocity = offset / flight[:, None]
    velocity[:, 2] += 0.5 * 9.81 * flight
    path, _ = integrate(start, velocity, FLIGHT_STEPS)
    direction = np.sign(situation.goal_x - situation.start[0]) or 1.0
    beyond = (path[:, :, 0] - situation.goal_x) * direction >= 0
    cross_step = np.where(beyond.any(axis=0), np.argmax(beyond, axis=0), FLIGHT_STEPS - 1)
    at_line = _line_crossing(path, start, cross_step, situation.goal_x)
    reaches_line = beyond.any(axis=0)
    inside_posts = np.abs(at_line[:, 1] - CENTRE_Y) < GOAL_WIDTH / 2 - BALL_RADIUS
    on_target = reaches_line & inside_posts & (at_line[:, 2] < GOAL_HEIGHT - BALL_RADIUS)

    outcome = np.where(on_target, GOAL, OFF_TARGET)
    resolve = cross_step.copy()
    blocker = np.full(n, -1)
    steps = np.arange(FLIGHT_STEPS)[:, None]
    for index, defender in enumerate(situation.blockers):
        gap = np.linalg.norm(path[:, :, :2] - defender, axis=2)
        reachable = (gap < BLOCK_REACH) & (path[:, :, 2] < 1.9) & (steps <= cross_step)
        reachable &= np.linalg.norm(path[:, :, :2] - situation.start[:2], axis=2) > 1.5
        hit = reachable.any(axis=0) & (uniforms[:, FIRST_BLOCK + index] < BLOCK_CHANCE) & (outcome != BLOCKED)
        first = np.argmax(reachable, axis=0)
        earlier = hit & ((blocker < 0) | (first < resolve))
        outcome = np.where(earlier, BLOCKED, outcome)
        resolve = np.where(earlier, first, resolve)
        blocker = np.where(earlier, index, blocker)

    keeper_gap = np.linalg.norm(path[:, :, :2] - situation.keeper_pos, axis=2)
    keeper_step = np.argmin(np.where(steps <= cross_step, keeper_gap, np.inf), axis=0)
    at_keeper = path[keeper_step, np.arange(n)]
    lateral = keeper_gap[keeper_step, np.arange(n)]
    effective = np.hypot(lateral, np.maximum(0.0, at_keeper[:, 2] - 1.8))
    reaction = situation.keeper_reaction * (0.8 + 0.4 * uniforms[:, KEEPER_REACTION])
    if situation.penalty:
        reaction = reaction * PENALTY_GUESS
    dive_time = np.maximum(0.0, (keeper_step + 1) * TICK - reaction)
    reach = np.minimum(KEEPER_STANDING_REACH + KEEPER_DIVE_SPEED * dive_time, KEEPER_MAX_REACH)
    reach *= 0.85 + 0.3 * situation.keeper_skill
    handling = 0.99 - (0.2 - 0.1 * situation.keeper_skill) * np.exp(-dive_time / 0.3)
    save_chance = handling / (1.0 + np.exp(-(reach - effective) / SAVE_SOFTNESS))
    saved = (outcome != BLOCKED) & on_target & (uniforms[:, KEEPER_HANDLING] < save_chance)
    clean = effective < CATCHABLE * reach
    outcome = np.where(saved, np.where(clean, SAVED, PARRIED), outcome)
    resolve = np.where(saved, keeper_step, resolve)
    return ShotBatch(outcome, resolve, blocker, velocity, on_target)


def expected_goal(situation: ShotSituation, rng: np.random.Generator) -> tuple[float, float]:
    """Monte Carlo P(goal) and P(on target) for this exact situation."""
    normals = rng.standard_normal((MONTE_CARLO_SAMPLES, 3))
    uniforms = rng.random((MONTE_CARLO_SAMPLES, uniform_columns(len(situation.blockers))))
    batch = resolve_shots(situation, normals, uniforms)
    return float(np.mean(batch.outcome == GOAL)), float(np.mean(batch.on_target))
