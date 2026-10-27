"""Gaining control of the ball and settling the pass that delivered it."""

import numpy as np

from frontroom_engine.pitch import CENTRE_Y, PITCH_LENGTH
from frontroom_engine.sim import referee
from frontroom_engine.sim.ball import TICK
from frontroom_engine.sim.core import Simulator, point
from frontroom_engine.sim.records import OffsideTruth
from frontroom_engine.sim.restarts import begin_restart
from frontroom_engine.sim.state import UnflaggedOffside

KEEPER_HOLD_TICKS = 30
QUICK_SHOT_RANGE = 20.0
"""Near goal there is no time to settle: receivers act in half their usual release time."""
ATTACKED_GOAL = np.array([PITCH_LENGTH, CENTRE_Y])


def _pass_detail(lofted: bool) -> dict[str, str]:
    return {"height": "high" if lofted else "ground"}


def fail_pass(sim: Simulator, end: np.ndarray) -> None:
    """Log the pending pass as unsuccessful, ending at `end` (an out-of-play point or a deflection)."""
    pending = sim.state.pending_pass
    if pending is None:
        return
    sim.state.pending_pass = None
    sim.act(
        pending.kind,
        pending.passer,
        pending.start,
        end=end,
        result="fail",
        body_part=pending.body_part,
        action_id=pending.action_id,
        tick=pending.tick,
        detail=_pass_detail(pending.lofted),
    )


def resolve_pass(sim: Simulator, receiver: int) -> bool:
    """Log the pending pass as received by `receiver`. Returns True if play stopped for offside."""
    s = sim.state
    pending = s.pending_pass
    if pending is None:
        return False
    s.pending_pass = None
    same_team = receiver // 11 == pending.passer // 11
    detail = _pass_detail(pending.lofted)
    latent: dict[str, float] = {}
    if same_team and receiver in pending.offside:
        margin = pending.offside[receiver]
        flagged = referee.flag_offside(sim, receiver, margin)
        s.offsides.append(OffsideTruth(pending.action_id, s.player_id(receiver), round(margin, 3), flagged))
        if flagged:
            sim.act(
                pending.kind,
                pending.passer,
                pending.start,
                end=s.pos[receiver],
                result="offside",
                body_part=pending.body_part,
                action_id=pending.action_id,
                tick=pending.tick,
                detail=detail,
            )
            begin_restart(sim, "free_kick", 1 - receiver // 11, s.pos[receiver], reason="offside")
            return True
        s.unflagged_offside = UnflaggedOffside(pending.action_id, receiver, margin, point(s.pos[receiver]))
        latent["offsideMargin"] = round(margin, 3)
    if same_team:
        detail["receiver"] = s.player_id(receiver)
    sim.act(
        pending.kind,
        pending.passer,
        pending.start,
        end=s.ball_pos[:2],
        result="success" if same_team else "fail",
        body_part=pending.body_part,
        action_id=pending.action_id,
        tick=pending.tick,
        detail=detail,
        latent=latent,
    )
    if not same_team:
        sim.act("interception", receiver, s.ball_pos[:2], result="success")
    return False


def gain_control(sim: Simulator, slot: int) -> None:
    """`slot` now has the ball: settle the pass, set the first touch and when he can next act."""
    s = sim.state
    if resolve_pass(sim, slot):
        return
    team = slot // 11
    sim.change_possession(team)
    s.owner = slot
    s.take_on = None
    s.last_touch = slot
    s.intercept_targets = {}
    u = sim.tape.uniform("control", s.tick, slot)
    heavy = u[0] > 0.35 + 0.6 * s.traits["first_touch"][slot]
    s.heavy_touch_until = s.tick + 6 if heavy else s.tick
    tempo = sim.setup.team(team).style.tempo
    release = s.traits["release_time"][slot] * (2.2 - 0.8 * tempo) * (0.8 + 0.8 * u[1]) + (
        0.3 if heavy else 0.0
    )
    if np.linalg.norm(sim.relative(s.pos[slot], team) - ATTACKED_GOAL) < QUICK_SHOT_RANGE:
        release *= 0.5
    s.next_decision_tick = s.tick + max(1, round(release / TICK))
    s.carry_start, s.carry_start_tick = point(s.pos[slot]), s.tick
    s.carry_target = s.pos[slot] + np.array([2.0 * sim.sign(team), 0.0])
    s.carry_speed = min(float(np.linalg.norm(s.vel[slot])), 3.0)
    if slot % 11 == 0 and referee.in_own_box(sim, slot):
        s.set_piece = "keeper"
        s.next_decision_tick += KEEPER_HOLD_TICKS + int(20 * u[1])
