"""The ball carrier's tick: keeping the ball, being pressed and tackled, and acting on decisions."""

import numpy as np

from frontroom_engine.sim import referee
from frontroom_engine.sim.ball import TICK, ground_launch_speed, lofted_launch, rotate, velocity_towards
from frontroom_engine.sim.core import Simulator
from frontroom_engine.sim.decide import decide
from frontroom_engine.sim.launch import launch, start_pass
from frontroom_engine.sim.options import Option, ground_arrival_speed
from frontroom_engine.sim.outcomes import take_shot
from frontroom_engine.sim.possession import gain_control
from frontroom_engine.sim.setup import HOME_EDGE

TACKLE_RANGE = 1.5
TACKLE_RATE = 0.9
TACKLE_COOLDOWN = 10
PRESS_RANGE = 4.0
PRESS_CLOSING_SPEED = 3.0
PRESS_COOLDOWN = 50
DANGER_RANGE = 2.5
DANGER_REACTION_TICKS = 4
BOX_CAUTION = 0.2
BOX_COMMITMENT = 1.4
"""...but they engage more often, because a carrier in the box has to be stopped."""
"""Defenders in their own box dive in far less: a foul there is a penalty."""
THROW_ANGLE = 20.0
PASS_EVENT = {"pass": "pass", "long": "pass", "cross": "cross", "clear": "clearance"}
PASS_RESTARTS = ("throw_in", "corner", "goal_kick", "free_kick")


def _attach_ball(sim: Simulator, carrier: int) -> None:
    s = sim.state
    velocity = s.vel[carrier]
    speed = float(np.linalg.norm(velocity))
    heading = velocity / speed if speed > 0.3 else np.array([float(sim.sign(carrier // 11)), 0.0])
    s.ball_pos = np.array([*(s.pos[carrier] + 0.5 * heading), 0.11])
    s.ball_vel = np.array([*velocity, 0.0])


def _detect_presses(sim: Simulator, carrier: int) -> None:
    """A press is logged when an opponent closes on the carrier quickly from within a few metres."""
    s = sim.state
    for rival in sim.active_slots(1 - carrier // 11):
        offset = s.pos[carrier] - s.pos[rival]
        distance = float(np.linalg.norm(offset))
        if distance > PRESS_RANGE or s.press_cooldown[rival] > s.tick or distance < 1e-6:
            continue
        closing = float((s.vel[rival] - s.vel[carrier]) @ (offset / distance))
        if closing > PRESS_CLOSING_SPEED:
            s.press_cooldown[rival] = s.tick + PRESS_COOLDOWN
            sim.act(
                "press", rival, s.pos[rival], end=s.pos[carrier], detail={"onPlayer": s.player_id(carrier)}
            )


def _settle_take_on(sim: Simulator, carrier: int, defender: int, won: bool) -> None:
    s = sim.state
    if s.take_on is not None and s.take_on[1] == defender:
        action_id = s.take_on[0]
        s.take_on = None
        sim.act(
            "take_on",
            carrier,
            s.pos[carrier],
            result="success" if won else "fail",
            action_id=action_id,
            detail={"againstPlayer": s.player_id(defender)},
        )


def _contest(sim: Simulator, carrier: int) -> bool:
    """Opponents within reach may tackle. Returns True if the carrier lost the ball or play stopped."""
    s = sim.state
    rivals = [
        r
        for r in sim.active_slots(1 - carrier // 11)
        if s.tackle_cooldown[r] <= s.tick and not sim.is_withheld(r)
    ]
    for rival in sorted(rivals, key=lambda r: float(np.linalg.norm(s.pos[r] - s.ball_pos[:2]))):
        if np.linalg.norm(s.pos[rival] - s.ball_pos[:2]) > TACKLE_RANGE:
            break
        heavy = s.heavy_touch_until > s.tick
        sign = sim.sign(carrier // 11)
        goal_side = (s.pos[rival][0] - s.pos[carrier][0]) * sign > 0.3
        committed = BOX_COMMITMENT if referee.in_own_box(sim, rival) else 1.0
        hazard = (
            TACKLE_RATE
            * (0.4 + s.traits["tackling"][rival])
            * (1.5 if heavy else 1.0)
            * (1.5 if goal_side else 1.0)
        )
        hazard *= committed
        u = sim.tape.uniform("tackle", s.tick, rival)
        if u[0] > 1.0 - np.exp(-hazard * TICK):
            continue
        from_behind = (s.pos[rival][0] - s.pos[carrier][0]) * sign < -0.3
        foul_chance = (
            0.045
            + 0.12 * (1 - s.traits["discipline"][rival])
            + (0.1 if from_behind else 0.0)
            + 0.1 * (1 - s.energy[rival])
        )
        if referee.in_own_box(sim, rival):
            foul_chance *= BOX_CAUTION
        if u[1] < foul_chance:
            sim.log_carry(carrier)
            _settle_take_on(sim, carrier, rival, won=True)
            referee.foul(sim, rival, carrier)
            return True
        duel = s.traits["tackling"][rival] - s.traits["dribbling"][carrier]
        success = np.clip(0.6 + 0.45 * duel + (0.2 if heavy else 0.0), 0.1, 0.9)
        if u[2] >= success:
            s.tackle_cooldown[rival] = s.tick + TACKLE_COOLDOWN
            sim.act("tackle", rival, s.pos[rival], result="fail", detail={"onPlayer": s.player_id(carrier)})
            _settle_take_on(sim, carrier, rival, won=True)
            continue
        sim.log_carry(carrier)
        sim.act("tackle", rival, s.pos[rival], result="success", detail={"onPlayer": s.player_id(carrier)})
        _settle_take_on(sim, carrier, rival, won=False)
        if u[3] < 0.5:
            gain_control(sim, rival)
        else:
            away = s.pos[rival] - s.pos[carrier]
            loose = rotate(np.array([*away, 0.0]), (u[3] - 0.75) * 2.0)
            loose = loose / max(float(np.linalg.norm(loose)), 1e-6) * (4.0 + 3.0 * u[3])
            launch(sim, loose, rival)
        return True
    return False


def _pass_velocity(sim: Simulator, carrier: int, option: Option, end: np.ndarray) -> np.ndarray:
    s = sim.state
    team = carrier // 11
    start = s.ball_pos
    distance = float(np.linalg.norm(end - start[:2]))
    throw = s.set_piece == "throw_in"
    angle = THROW_ANGLE if throw else option.loft
    if angle > 0:
        speed, _ = lofted_launch(distance, angle)
    else:
        tempo = sim.setup.team(team).style.tempo
        speed = float(
            ground_launch_speed(np.array(distance), ground_arrival_speed(np.array(distance), tempo))
        )
    rivals = sim.active_slots(1 - team)
    nearest = min(float(np.linalg.norm(s.pos[r] - s.pos[carrier])) for r in rivals)
    pressure = float(np.clip((4.5 - nearest) / 4.5, 0.0, 1.0))
    noise = s.traits["pass_noise"][carrier] * (1 + 1.2 * pressure) * (0.6 + distance / 80.0)
    noise *= (1.5 if option.kind in ("cross", "clear") else 1.0) * (1.0 - HOME_EDGE if team == 0 else 1.0)
    n = sim.tape.normal("pass", s.tick, carrier)
    speed *= 1.0 + (0.03 + 0.3 * s.traits["pass_noise"][carrier]) * n[1]
    velocity = velocity_towards(start, end, speed, angle + (3.0 * n[2] if angle > 0 else 0.0))
    return rotate(velocity, noise * n[0])


def _execute(sim: Simulator, carrier: int, option: Option, action_id: int) -> None:
    s = sim.state
    team = carrier // 11
    end = sim.relative(option.end, team)
    restart = s.set_piece
    s.set_piece = None
    if option.kind == "shot":
        take_shot(
            sim, carrier, action_id, kind="penalty" if restart == "penalty" else "shot", set_piece=restart
        )
        return
    if option.kind in PASS_EVENT:
        sim.log_carry(carrier)
        kind = restart if restart in PASS_RESTARTS else PASS_EVENT[option.kind]
        body_part = "other" if restart == "throw_in" else "foot"
        velocity = _pass_velocity(sim, carrier, option, end)
        start_pass(
            sim,
            carrier,
            option.target_slot,
            action_id,
            kind,
            lofted=option.loft > 0 or restart == "throw_in",
            body_part=body_part,
        )
        launch(sim, velocity, carrier, option.target_slot)
        return
    s.carry_target = end
    s.carry_speed = option.speed
    duration = float(np.linalg.norm(end - s.pos[carrier])) / max(option.speed, 0.5)
    s.next_decision_tick = s.tick + max(4, round(duration / TICK))
    if option.kind == "take_on":
        s.take_on = (action_id, option.target_slot, s.next_decision_tick + 5)


def carrier_tick(sim: Simulator) -> None:
    s = sim.state
    carrier = s.owner
    _attach_ball(sim, carrier)
    _detect_presses(sim, carrier)
    if s.set_piece is None and _contest(sim, carrier):
        return
    if s.take_on is not None and s.tick > s.take_on[2]:
        defender = s.take_on[1]
        if (s.pos[carrier][0] - s.pos[defender][0]) * sim.sign(carrier // 11) > 1.0:
            _settle_take_on(sim, carrier, defender, won=True)
        else:
            s.take_on = None
    rivals = sim.active_slots(1 - carrier // 11)
    danger = min(float(np.linalg.norm(s.pos[r] - s.pos[carrier])) for r in rivals) < DANGER_RANGE
    if danger and s.set_piece is None:
        s.next_decision_tick = min(s.next_decision_tick, s.tick + DANGER_REACTION_TICKS)
    if s.tick >= s.next_decision_tick:
        forced = sim.forced_option(carrier)
        option, action_id = decide(sim.state, sim.setup, sim.tape, carrier, s.set_piece, forced)
        _execute(sim, carrier, option, action_id)
