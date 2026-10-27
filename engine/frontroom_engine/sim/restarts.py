"""Dead-ball phases: players walk into set-piece shapes, the ball is brought back, play restarts.

The dead time before each restart is drawn per restart type. It is the main lever on the
ball-in-play share (about 55 % in elite football).
"""

import numpy as np

from frontroom_engine.pitch import (
    CENTRE_X,
    CENTRE_Y,
    PENALTY_AREA_HALF_WIDTH,
    PENALTY_SPOT_DISTANCE,
    PITCH_LENGTH,
)
from frontroom_engine.sim.ball import TICK
from frontroom_engine.sim.core import Simulator, point
from frontroom_engine.sim.motion import steer
from frontroom_engine.sim.offball import offball_targets
from frontroom_engine.sim.state import Restart

DELAY_SECONDS: dict[str, tuple[float, float]] = {
    "throw_in": (11.0, 12.0),
    "goal_kick": (19.0, 15.0),
    "corner": (28.0, 14.0),
    "free_kick": (20.0, 16.0),
    "penalty": (60.0, 30.0),
    "kick_off": (55.0, 25.0),
}
REASON_DELAY_SECONDS: dict[str, tuple[float, float]] = {
    "offside": (12.0, 8.0),
    "var": (80.0, 30.0),
    "treatment": (40.0, 50.0),
    "period": (1.0, 0.0),
}
DANGEROUS_FREE_KICK = 35.0
BALL_RETURN_SPEED = 8.0
DEAD_BALL_JOG = 3.0
BOX_ZONES = ((99.0, 31.0), (99.0, 37.0), (95.0, 34.0), (93.0, 28.0), (93.0, 40.0), (88.0, 34.0))
AERIAL_ROLES = ("ST", "CB", "AM", "CM", "LW", "RW")


def _taker(sim: Simulator, kind: str, team: int, spot: np.ndarray) -> int:
    s = sim.state
    outfield = [slot for slot in sim.active_slots(team) if slot % 11 != 0]
    if kind == "goal_kick":
        return sim.keeper(team)
    if kind == "kick_off":
        strikers = [slot for slot in outfield if sim.setup.team(team).roles[slot % 11] == "ST"]
        if strikers:
            return strikers[0]
    if kind == "penalty":
        return min(outfield, key=lambda slot: s.traits["finishing"][slot])
    return min(outfield, key=lambda slot: float(np.linalg.norm(s.pos[slot] - spot)))


def begin_restart(sim: Simulator, kind: str, team: int, spot: np.ndarray, reason: str = "") -> None:
    s = sim.state
    u = sim.tape.uniform("restart", s.tick, 0)
    base, spread = REASON_DELAY_SECONDS.get(reason, DELAY_SECONDS[kind])
    delay = base + spread * u[0]
    goal_distance = np.linalg.norm(sim.relative(np.asarray(spot), team) - np.array([PITCH_LENGTH, CENTRE_Y]))
    if kind == "free_kick" and reason == "" and goal_distance < DANGEROUS_FREE_KICK:
        delay += 15.0
    s.phase = "dead"
    s.owner = -1
    s.pending_pass = None
    s.pending_shot = None
    s.take_on = None
    s.intercept_targets = {}
    s.ball_path = np.zeros((0, 3))
    s.ball_path_vel = np.zeros((0, 3))
    s.ball_vel = np.zeros(3)
    sim.change_possession(team)
    s.restart = Restart(kind, team, point(np.asarray(spot)), s.tick + round(delay / TICK))
    s.restart_taker = _taker(sim, kind, team, np.asarray(spot))


def _in_box(relative: np.ndarray) -> np.ndarray:
    return (relative[:, 0] > PITCH_LENGTH - 16.5) & (
        np.abs(relative[:, 1] - CENTRE_Y) < PENALTY_AREA_HALF_WIDTH
    )


def _kick_off_shape(sim: Simulator, targets: np.ndarray, kicking: int) -> None:
    for team in (0, 1):
        slots = sim.active_slots(team)
        rel = sim.relative(targets[slots], team)
        rel[:, 0] = np.minimum(rel[:, 0], CENTRE_X - 1.0)
        if team != kicking:
            offset = rel - np.array([CENTRE_X, CENTRE_Y])
            gap = np.linalg.norm(offset, axis=1, keepdims=True)
            rel = np.where(
                gap < 9.5, np.array([CENTRE_X, CENTRE_Y]) + offset / np.maximum(gap, 1e-6) * 9.5, rel
            )
            rel[:, 0] = np.minimum(rel[:, 0], CENTRE_X - 1.0)
        targets[slots] = sim.relative(rel, team)


def _box_shape(sim: Simulator, targets: np.ndarray, attacking: int, taker: int) -> None:
    """Attackers attack the box zones; defenders go goal-side of them and the keeper takes his line."""
    roles = sim.setup.team(attacking).roles
    runners = [s for s in sim.active_slots(attacking) if s != taker and roles[s % 11] in AERIAL_ROLES][
        : len(BOX_ZONES)
    ]
    zones = np.array(BOX_ZONES[: len(runners)])
    targets[runners] = sim.relative(zones, attacking)
    defenders = [s for s in sim.active_slots(1 - attacking) if s % 11 != 0]
    for zone, marker in zip(zones, defenders, strict=False):
        targets[marker] = sim.relative(zone + np.array([1.2, 0.0]), attacking)
    targets[sim.keeper(1 - attacking)] = sim.relative(np.array([PITCH_LENGTH - 0.5, CENTRE_Y]), attacking)


def _penalty_shape(sim: Simulator, targets: np.ndarray, attacking: int, taker: int) -> None:
    keeper = sim.keeper(1 - attacking)
    for team in (0, 1):
        slots = [s for s in sim.active_slots(team) if s not in (taker, keeper)]
        rel = sim.relative(targets[slots], attacking)
        inside = _in_box(rel)
        rel[inside, 0] = PITCH_LENGTH - 18.0
        targets[slots] = sim.relative(rel, attacking)
    targets[keeper] = sim.relative(np.array([PITCH_LENGTH - 0.2, CENTRE_Y]), attacking)


def restart_targets(sim: Simulator) -> tuple[np.ndarray, np.ndarray]:
    s = sim.state
    restart = s.restart
    targets, speeds = offball_targets(s, sim.setup, sim.tape)
    spot = np.array(restart.spot)
    rel_spot = sim.relative(spot, restart.team)
    if restart.kind == "kick_off":
        _kick_off_shape(sim, targets, restart.team)
    elif restart.kind == "penalty":
        _penalty_shape(sim, targets, restart.team, s.restart_taker)
    elif restart.kind == "corner" or (
        restart.kind == "free_kick" and rel_spot[0] > PITCH_LENGTH - DANGEROUS_FREE_KICK
    ):
        _box_shape(sim, targets, restart.team, s.restart_taker)
    behind = sim.relative(rel_spot - np.array([0.6, 0.0]), restart.team)
    targets[s.restart_taker] = behind if restart.kind != "throw_in" else spot
    speeds = np.minimum(speeds, DEAD_BALL_JOG)
    speeds[s.restart_taker] = 4.5
    return targets, speeds


def place_for_kick_off(sim: Simulator, kicking: int) -> None:
    """Put everyone straight into kick-off positions; only used at the start of each half."""
    s = sim.state
    begin_restart(sim, "kick_off", kicking, np.array([CENTRE_X, CENTRE_Y]), reason="period")
    s.ball_pos = np.array([CENTRE_X, CENTRE_Y, 0.0])
    s.ball_history[:] = s.ball_pos[:2]
    targets, _ = restart_targets(sim)
    s.pos = targets.copy()
    s.vel = np.zeros_like(s.vel)


def dead_tick(sim: Simulator) -> None:
    s = sim.state
    restart = s.restart
    targets, speeds = restart_targets(sim)
    inactive = ~s.active
    targets[inactive], speeds[inactive] = s.pos[inactive], 0.0
    top = s.traits["top_speed"] * (0.88 + 0.12 * s.energy)
    s.pos, s.vel = steer(s.pos, s.vel, targets, speeds, top, s.traits["acceleration"])
    spot = np.array(restart.spot)
    offset = spot - s.ball_pos[:2]
    step = min(float(np.linalg.norm(offset)), BALL_RETURN_SPEED * TICK)
    direction = offset / max(float(np.linalg.norm(offset)), 1e-9)
    s.ball_pos = np.array([*(s.ball_pos[:2] + direction * step), 0.0])
    s.ball_vel = np.array([*(direction * step / TICK), 0.0])
    taker = s.restart_taker
    ready = (
        s.tick >= restart.ready_tick and np.linalg.norm(s.pos[taker] - targets[taker]) < 1.0 and step < 1e-6
    )
    if ready:
        s.phase = "play"
        s.owner = taker
        s.last_touch = taker
        s.set_piece = restart.kind
        s.next_decision_tick = s.tick + 1
        s.carry_start, s.carry_start_tick = point(s.pos[taker]), s.tick
        s.carry_target, s.carry_speed = s.pos[taker].copy(), 0.0
        s.ball_pos = np.array([*spot, 0.11])
        s.restart = None


def penalty_spot(sim: Simulator, team: int) -> np.ndarray:
    return sim.relative(np.array([PITCH_LENGTH - PENALTY_SPOT_DISTANCE, CENTRE_Y]), team)
