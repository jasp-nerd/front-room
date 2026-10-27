"""The ball while nobody has it: control attempts, deflections and headers, tick by tick.

Anyone within reach of the segment the ball travelled this tick gets a chance to control it.
The chance shrinks with ball speed and grows with first-touch skill; an opponent who touches
it without controlling it may deflect it. That is all "pass success" is.
"""

import numpy as np

from frontroom_engine.pitch import CENTRE_Y
from frontroom_engine.sim import referee
from frontroom_engine.sim.ball import TICK, integrate, rotate, velocity_towards
from frontroom_engine.sim.core import Simulator
from frontroom_engine.sim.launch import PATH_STEPS, assign_chasers, launch, start_pass
from frontroom_engine.sim.outcomes import (
    crossed_boundary,
    parry_velocity,
    resolve_shot,
    shot_detail,
    take_shot,
)
from frontroom_engine.sim.possession import fail_pass, gain_control, resolve_pass

HEADER_HEIGHT = 1.7
REASSIGN_EVERY = 5
STALLED_SHOT_SPEED = 2.0
COMFORTABLE_SPEED = 9.0
SPEED_FALLOFF = 6.0
"""Control gets hard quickly above a comfortable ball speed; a fast ball is more often blocked."""
DEFLECTION_CHANCE = 0.6
AERIAL_EDGE = 1.0
"""Metres of reach that the best header of the ball gains over a poor one in an aerial duel."""
FIRST_TIME_CLEARANCE = 0.8
"""Share of delivered balls a defender in his own box clears first time instead of controlling."""
BEHIND_DEPTH = 9.0
CLEAR_BEHIND_CHANCE = 0.4
"""Close to his own line, a defender under a delivered ball often settles for putting it behind."""
DEEP_CLEARANCE = 20.0
"""Inside this depth a defender can only glance the ball on, so it keeps much of its line."""


def _advance(sim: Simulator) -> None:
    """Move the ball one tick along its predicted path, extending the path when it runs out."""
    s = sim.state
    s.ball_pos, s.ball_vel = s.ball_path[0].copy(), s.ball_path_vel[0].copy()
    s.ball_path, s.ball_path_vel = s.ball_path[1:], s.ball_path_vel[1:]
    if len(s.ball_path) == 0:
        path, path_vel = integrate(s.ball_pos, s.ball_vel, PATH_STEPS)
        s.ball_path, s.ball_path_vel = path[:, 0], path_vel[:, 0]


def _deflect(sim: Simulator, slot: int) -> None:
    """A touch without control. Crosses keep more of their pace, which is how many corners happen."""
    s = sim.state
    cross = s.pending_pass is not None and s.pending_pass.kind in ("cross", "corner")
    fail_pass(sim, s.ball_pos[:2])
    n = sim.tape.normal("control", s.tick, slot)
    deflected = rotate(s.ball_vel, (1.0 if cross else 0.7) * n[0]) * (0.7 if cross else 0.5)
    deflected[2] = abs(deflected[2]) * 0.5 + 0.5
    launch(sim, deflected, slot)


def _punch(sim: Simulator, keeper: int) -> None:
    """A keeper who cannot hold the ball pushes it away from goal and wide."""
    s = sim.state
    fail_pass(sim, s.ball_pos[:2])
    sim.act(
        "keeper_save",
        keeper,
        s.ball_pos[:2],
        result="success",
        body_part="other",
        detail={"outcome": "punched"},
    )
    launch(sim, parry_velocity(sim, keeper), keeper)


def _first_time(sim: Simulator, slot: int, body_part: str) -> None:
    """Play the ball first time: attackers in the box shoot, defenders clear, others knock it on."""
    s = sim.state
    team = slot // 11
    if resolve_pass(sim, slot):
        return
    sim.change_possession(team)
    x, y = sim.relative(s.ball_pos[:2], team)
    if x > 88.5 and abs(y - CENTRE_Y) < 16.0:
        take_shot(sim, slot, s.new_action_id(), header=body_part == "head")
        return
    if x < BEHIND_DEPTH and sim.tape.uniform("control", s.tick, slot)[1] < CLEAR_BEHIND_CHANCE:
        side = 1.0 if y > CENTRE_Y else -1.0
        target = sim.relative(np.array([-5.0, y + 12.0 * side]), team)
        sim.act("clearance", slot, s.ball_pos[:2], end=target, result="success", body_part=body_part)
        launch(sim, velocity_towards(s.ball_pos, target, 14.0, 25.0), slot)
        return
    if x < 40.0:
        upfield = np.array([1.0, 0.3 if y > CENTRE_Y else -0.3])
        incoming = s.ball_vel[:2] * sim.sign(team)
        if x < DEEP_CLEARANCE:
            upfield = 0.4 * upfield / np.linalg.norm(upfield) + 0.6 * incoming / max(
                float(np.linalg.norm(incoming)), 1e-6
            )
        direction = upfield / max(float(np.linalg.norm(upfield)), 1e-6)
        target = sim.relative(np.array([x, y]) + 25.0 * direction, team)
        sim.act("clearance", slot, s.ball_pos[:2], end=target, result="success", body_part=body_part)
        launch(sim, velocity_towards(s.ball_pos, target, 13.0 if body_part == "head" else 20.0, 40.0), slot)
        return
    mates = [m for m in sim.active_slots(team) if m != slot and m % 11 != 0]
    distances = np.linalg.norm(s.pos[mates] - s.pos[slot], axis=1)
    receiver = mates[int(np.argmin(np.where(distances > 4.0, distances, np.inf)))]
    start_pass(sim, slot, receiver, s.new_action_id(), "pass", lofted=True, body_part=body_part)
    launch(sim, velocity_towards(s.ball_pos, s.pos[receiver], 11.0, 30.0), slot, receiver)


def _reach(sim: Simulator, slots: np.ndarray, heights: np.ndarray, keepers: np.ndarray) -> np.ndarray:
    """How far from the ball each player can still play it, given its height."""
    aerial = sim.state.traits["aerial"][slots]
    outfield = np.where(
        heights <= 1.0, 1.0, np.where(heights <= 1.9, 0.8, np.where(heights <= 2.6, 0.6 + 0.4 * aerial, 0.0))
    )
    return np.where(keepers, np.where(heights <= 2.8, 1.6, 0.0), outfield)


def try_control(sim: Simulator, previous: np.ndarray) -> None:
    s = sim.state
    segment = s.ball_pos[:2] - previous[:2]
    length2 = float(segment @ segment)
    kicker_blocked = s.tick < s.kicker_cooldown_until
    in_flight = (s.tick - s.launch_tick) * TICK
    kicking_team = s.last_touch // 11
    slots = np.array(
        [
            i
            for i in range(22)
            if s.active[i]
            and not (kicker_blocked and i == s.last_touch)
            and not sim.is_withheld(i)
            and (i // 11 == kicking_team or in_flight >= s.traits["reaction_time"][i])
        ]
    )
    if slots.size == 0:
        return
    offsets = s.pos[slots] - previous[:2]
    along = np.clip(offsets @ segment / length2, 0.0, 1.0) if length2 > 1e-9 else np.zeros(len(slots))
    gaps = np.linalg.norm(offsets - along[:, None] * segment, axis=1)
    heights = previous[2] + along * (s.ball_pos[2] - previous[2])
    keepers = np.array([slot % 11 == 0 and referee.in_own_box(sim, slot) for slot in slots])
    eligible = np.flatnonzero(gaps <= _reach(sim, slots, heights, keepers))
    speed = float(np.linalg.norm(s.ball_vel))
    pending = s.pending_pass
    receiver = pending.receiver if pending else -1
    delivered = pending is not None and pending.lofted
    jump = sim.tape.uniform_all("control", s.tick)[slots, 1]
    contest = gaps - np.where(heights > HEADER_HEIGHT, AERIAL_EDGE * s.traits["aerial"][slots] * jump, 0.0)
    for row in eligible[np.argsort(contest[eligible])]:
        slot = int(slots[row])
        if heights[row] > HEADER_HEIGHT and not keepers[row]:
            _first_time(sim, slot, "head")
            return
        under_pressure = (
            delivered
            and not keepers[row]
            and referee.in_own_box(sim, slot)
            and slot // 11 != pending.passer // 11
        )
        if under_pressure and jump[row] < FIRST_TIME_CLEARANCE:
            _first_time(sim, slot, "foot")
            return
        own_side = s.last_touch >= 0 and slot // 11 == s.last_touch // 11
        if keepers[row]:
            skill = 0.6 + 0.4 * s.traits["goalkeeping"][slot]
        else:
            skill = 0.55 + 0.45 * s.traits["first_touch"][slot]
        familiarity = 1.05 if slot == receiver else 1.0 if own_side else 0.7
        chance = skill * np.exp(-max(0.0, speed - COMFORTABLE_SPEED) / SPEED_FALLOFF) * familiarity
        u = sim.tape.uniform("control", s.tick, slot)
        if u[0] < chance:
            gain_control(sim, slot)
            return
        if keepers[row]:
            _punch(sim, slot)
            return
        if not own_side and u[1] < DEFLECTION_CHANCE:
            _deflect(sim, slot)
            return


def flight_tick(sim: Simulator) -> None:
    s = sim.state
    previous = s.ball_pos.copy()
    _advance(sim)
    shot = s.pending_shot
    if shot is not None and 0 <= shot.resolve_tick <= s.tick:
        resolve_shot(sim)
        return
    if crossed_boundary(sim, previous):
        return
    if shot is not None:
        if np.linalg.norm(s.ball_vel) > STALLED_SHOT_SPEED:
            return
        s.pending_shot = None
        sim.act(
            shot.kind,
            shot.shooter,
            shot.start,
            end=s.ball_pos[:2],
            result="fail",
            body_part=shot.body_part,
            action_id=shot.action_id,
            tick=shot.tick,
            detail=shot_detail(shot, "off_target"),
        )
    if s.tick % REASSIGN_EVERY == 0:
        receiver = s.pending_pass.receiver if s.pending_pass else -1
        assign_chasers(sim, receiver, s.last_touch if s.tick < s.kicker_cooldown_until else -1)
    try_control(sim, previous)
