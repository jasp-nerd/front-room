"""Officiating: offside flags, fouls and cards, added time and substitutions.

The assistant referee is a noisy observer: tight offsides are often missed on the field, which
is exactly what lets VAR overturn a goal later in the same possession.
"""

from dataclasses import replace

import numpy as np

from frontroom_engine.pitch import CENTRE_X, PITCH_LENGTH, PITCH_WIDTH, in_penalty_area
from frontroom_engine.sim.core import TICKS_PER_SECOND, Simulator
from frontroom_engine.sim.restarts import begin_restart, penalty_spot

FLAG_THRESHOLD = 0.3
FLAG_SHARPNESS = 0.12
RED_CARD_CHANCE = 0.003
MAX_SUBSTITUTIONS = 3
SUBSTITUTION_SECONDS = 15
TREATMENT_CHANCE = 0.15
"""Share of fouls after which the fouled player needs treatment before the free kick."""


def flag_offside(sim: Simulator, slot: int, margin: float) -> bool:
    u = sim.tape.uniform("referee", sim.state.tick, slot)[0]
    return bool(u < 1.0 / (1.0 + np.exp(-(margin - FLAG_THRESHOLD) / FLAG_SHARPNESS)))


def in_own_box(sim: Simulator, slot: int) -> bool:
    team = slot // 11
    own_goal_x = 0.0 if sim.sign(team) > 0 else PITCH_LENGTH
    x, y = sim.state.pos[slot]
    return in_penalty_area(float(x), float(y), own_goal_x)


def _send_off(sim: Simulator, slot: int) -> None:
    s = sim.state
    s.active[slot] = False
    s.pos[slot] = (CENTRE_X, -3.0)
    s.vel[slot] = 0.0


def _card(sim: Simulator, fouler: int, victim: int) -> None:
    s = sim.state
    u = sim.tape.uniform("referee", s.tick, fouler)
    breakaway = float(np.linalg.norm(s.vel[victim])) > 5.0
    yellow = 0.09 + 0.12 * (1.0 - s.traits["discipline"][fouler]) + (0.12 if breakaway else 0.0)
    red = RED_CARD_CHANCE if fouler % 11 != 0 else 0.0
    if u[1] < red:
        colour = "red"
    elif u[1] < red + yellow:
        s.yellow_cards[fouler] += 1
        colour = "second_yellow" if s.yellow_cards[fouler] >= 2 else "yellow"
    else:
        return
    sim.act("card", fouler, s.pos[fouler], detail={"colour": colour})
    if colour != "yellow":
        _send_off(sim, fouler)


def foul(sim: Simulator, fouler: int, victim: int) -> None:
    """Stop play for a foul by `fouler` on `victim`: card decision, then a free kick or a penalty."""
    s = sim.state
    spot = s.pos[victim].copy()
    sim.act("foul", fouler, spot, result="success", detail={"onPlayer": s.player_id(victim)})
    _card(sim, fouler, victim)
    team = victim // 11
    attacked_goal_x = PITCH_LENGTH if sim.sign(team) > 0 else 0.0
    if in_penalty_area(float(spot[0]), float(spot[1]), attacked_goal_x):
        begin_restart(sim, "penalty", team, penalty_spot(sim, team))
    else:
        clamped = np.clip(spot, [0.5, 0.5], [PITCH_LENGTH - 0.5, PITCH_WIDTH - 0.5])
        treatment = sim.tape.uniform("referee", s.tick, victim)[3] < TREATMENT_CHANCE
        begin_restart(sim, "free_kick", team, clamped, reason="treatment" if treatment else "")


def added_minutes(sim: Simulator) -> int:
    """Stoppage time grows with the goals, cards and substitutions of the half."""
    s = sim.state
    stoppages = sum(
        1 for a in s.actions if a.period == s.period and a.kind in ("goal", "card", "substitution")
    )
    u = sim.tape.uniform("referee", s.tick, 0)[2]
    if s.period == 1:
        return int(np.clip(1 + stoppages / 3 + 2 * u, 1, 5))
    return int(np.clip(3 + stoppages / 4 + 3 * u, 3, 8))


def plan_substitutions(sim: Simulator) -> None:
    """Draw each side's substitution minutes once, at kick-off."""
    for team in (0, 1):
        u = sim.tape.uniform("referee", 0, 11 * team + 1)
        sim.state.sub_windows[team] = [int(58 + 12 * u[0]), int(68 + 10 * u[1]), int(78 + 8 * u[2])]


def _substitute(sim: Simulator, team: int) -> bool:
    s = sim.state
    club = sim.setup.team(team).club
    outfield = [
        slot
        for slot in sim.active_slots(team)
        if slot % 11 != 0 and s.player_id(slot) not in sim.setup.kept_on
    ]
    if not outfield:
        return False
    leaving = min(outfield, key=lambda slot: s.energy[slot])
    role = sim.setup.team(team).roles[leaving % 11]
    bench = [p for p in club.bench() if p.id not in s.substituted_in and p.role.value != "GK"]
    if not bench:
        return False
    entering = next((p for p in bench if p.role.value == role), bench[0])
    leaving_id = s.player_id(leaving)
    s.set_player(leaving, entering)
    s.substituted_in.append(entering.id)
    s.energy[leaving] = 1.0
    s.pos[leaving] = (CENTRE_X, 0.5)
    s.vel[leaving] = 0.0
    s.subs_made[team] += 1
    sim.act(
        "substitution", leaving, s.pos[leaving], detail={"playerOut": leaving_id, "playerIn": entering.id}
    )
    return True


def substitutions_due(sim: Simulator) -> None:
    """Make any substitution whose planned minute has passed; called when the ball goes dead."""
    s = sim.state
    if s.period != 2:
        return
    for team in (0, 1):
        while s.subs_made[team] < MAX_SUBSTITUTIONS and sim.minute >= s.sub_windows[team][s.subs_made[team]]:
            if not _substitute(sim, team):
                return
            if s.restart is not None:
                delay = SUBSTITUTION_SECONDS * TICKS_PER_SECOND
                s.restart = replace(s.restart, ready_tick=s.restart.ready_tick + delay)
