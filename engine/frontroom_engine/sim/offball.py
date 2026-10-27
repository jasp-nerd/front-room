"""Off-ball movement: formation anchors, marking with lapses, pressing triggers and runs.

Every player gets a target point and a desired speed each tick. The on-ball logic later
overrides the targets of the carrier, pass receivers and interceptors. Targets are computed
from the ball position as it was a reaction time ago, so nobody responds instantly.
"""

import numpy as np

from frontroom_engine.pitch import CENTRE_X, CENTRE_Y, PITCH_LENGTH
from frontroom_engine.sim.ball import TICK
from frontroom_engine.sim.geometry import attack_sign, to_attack_frame
from frontroom_engine.sim.motion import time_to_reach
from frontroom_engine.sim.noise import NoiseTape
from frontroom_engine.sim.setup import MatchSetup, TeamSetup
from frontroom_engine.sim.state import MatchState, team_slots

JOG = 3.2
RUN = 5.5
RECOVERY = 6.5
WALK_GAIN = 0.5
DRIFT_PULL = 0.3
DRIFT_SPREAD = 0.9
LAPSE_RATE = 0.05
RUN_RATE = 0.9
FORWARD_ROLES = ("ST", "RW", "LW", "AM")
SCREEN_DEPTH = (35.0, 62.0)
SCREEN_HALF_WIDTH = 15.0
SCREEN_REACH = 12.0
"""A holding midfielder steps out to a central carrier 35-62 m from his goal, if within 12 m of him."""
TRAP_DEPTH = 28.0
"""An opponent on the ball this close to his own goal line is trapped by the two nearest players."""
LOW_BLOCK_DEPTH = 40.0
"""With the ball this close to their own goal, defending sides squeeze into a shorter, narrower block."""
BOX_MARKING = 0.85
OFFSIDE_DISCIPLINE = 0.3
KEEPER_RUSH_RANGE = 14.0
KEEPER_RUSH_SHARE = 0.3
KEEPER_LATERAL_RANGE = 2.5
"""A keeper covers the near post from inside the goal mouth rather than following a wide ball out."""
BOX_RUN_TICKS = 15
MISTIMED_RUN = 1.0
"""Runners sometimes set off from just beyond the line, which is where offsides come from."""
GOAL_SIDE_GAP = 1.2
BALL_SIDE_GAP = 0.8
KEEPER_URGENCY = 2.0
"""Keepers close the gap to their ideal position four times as eagerly as outfield players."""


def _anchors(team: TeamSetup, ball: np.ndarray, in_possession: bool) -> np.ndarray:
    """Formation anchors in the attacking frame for a ball at `ball` (also attacking frame)."""
    bx, by = ball
    style = team.style
    if in_possession:
        centre = 22.0 + 0.5 * bx + 8.0 * (style.line_height - 0.5)
        length, width, slide = 1.25, 0.78 + 0.2 * style.width, 0.15
    else:
        press_push = 10.0 * (style.press - 0.5) if bx > 55 else 0.0
        centre = 12.0 + 0.45 * bx + 14.0 * (style.line_height - 0.5) + press_push
        if bx < LOW_BLOCK_DEPTH:
            length, width, slide = 0.85, 0.55 + 0.1 * style.width, 0.4
        else:
            length, width, slide = 1.05, 0.62 + 0.1 * style.width, 0.35
    x = np.clip(centre + team.depth * length, 3.0, PITCH_LENGTH - 3.0)
    y = np.clip(CENTRE_Y + (team.lateral - CENTRE_Y) * width + slide * (by - CENTRE_Y), 2.0, 66.0)
    if in_possession:
        overlap = np.isin(team.roles, ("RB", "LB")) & (
            np.sign(team.lateral - CENTRE_Y) == np.sign(by - CENTRE_Y)
        )
        x = np.where(overlap & (bx > 60), x + 10.0 * style.width, x)
    return np.stack([x, y], axis=1)


def _goalkeeper(ball: np.ndarray, in_possession: bool) -> np.ndarray:
    own_goal = np.array([0.0, CENTRE_Y])
    if in_possession and ball[0] > CENTRE_X:
        return np.array([14.0 + 0.1 * (ball[0] - CENTRE_X), CENTRE_Y])
    offset = ball - own_goal
    distance = max(float(np.linalg.norm(offset)), 1e-6)
    if distance < KEEPER_RUSH_RANGE:
        depth = max(1.0, distance - 3.0) * KEEPER_RUSH_SHARE
    else:
        depth = float(np.clip(0.12 * distance, 1.0, 6.0))
    target = own_goal + offset / distance * depth
    target[1] = np.clip(target[1], CENTRE_Y - KEEPER_LATERAL_RANGE, CENTRE_Y + KEEPER_LATERAL_RANGE)
    return target


def offside_line(state: MatchState, team: int, sign: int) -> float:
    """Attacking-frame x of the second-last opponent, never inside the attackers' own half."""
    opponents = [s for s in team_slots(1 - team) if state.active[s]]
    xs = np.sort(to_attack_frame(state.pos[opponents], sign)[:, 0])
    return max(float(xs[-2]), CENTRE_X)


def _update_lapses(state: MatchState, tape: NoiseTape) -> None:
    u = tape.uniform_all("lapse", state.tick)
    hazard = LAPSE_RATE * (1.0 - state.traits["concentration"]) * (1.0 + 1.5 * (1.0 - state.energy)) * TICK
    starting = (state.lapse_until <= state.tick) & (u[:, 0] < hazard)
    state.lapse_until = np.where(starting, state.tick + (15 + 25 * u[:, 1]).astype(int), state.lapse_until)


def _mark(state: MatchState, team: int, sign: int, anchors: np.ndarray, ball: np.ndarray) -> np.ndarray:
    """Pull outfield anchors goal-side of the nearest opponent; lapsing players ball-watch instead."""
    slots = np.array(team_slots(team))[1:]
    rivals = [s for s in team_slots(1 - team)[1:] if state.active[s]]
    if not rivals:
        return anchors
    attackers = to_attack_frame(state.pos[rivals], sign)
    gaps = np.linalg.norm(anchors[1:, None, :] - attackers[None, :, :], axis=2)
    nearest = np.argmin(gaps, axis=1)
    marked = attackers[nearest]
    goal_side = np.array([0.0, CENTRE_Y]) - marked
    goal_side /= np.maximum(np.linalg.norm(goal_side, axis=1, keepdims=True), 1e-6)
    ball_side = ball - marked
    ball_side /= np.maximum(np.linalg.norm(ball_side, axis=1, keepdims=True), 1e-6)
    mark_points = marked + GOAL_SIDE_GAP * goal_side + BALL_SIDE_GAP * ball_side
    near_ball = np.linalg.norm(marked - ball, axis=1) < 35.0
    near_goal = np.linalg.norm(marked - np.array([0.0, CENTRE_Y]), axis=1) < 25.0
    weight = np.where(near_ball, 0.6, 0.3)
    weight = np.where(near_goal, BOX_MARKING, weight)
    weight = np.where(gaps[np.arange(len(nearest)), nearest] < 14.0, weight, 0.0)
    weight = np.where(state.lapse_until[slots] > state.tick, 0.0, weight)
    out = anchors.copy()
    out[1:] += weight[:, None] * (mark_points - anchors[1:])
    return out


def _screening_midfielder(
    state: MatchState, setup: MatchSetup, team: int, ball: np.ndarray, carrier: int
) -> int:
    """The holding midfielder, if the carrier is driving at him through the zone he screens; else -1."""
    central = abs(ball[1] - CENTRE_Y) < SCREEN_HALF_WIDTH
    if not (central and SCREEN_DEPTH[0] <= ball[0] <= SCREEN_DEPTH[1]):
        return -1
    roles = setup.team(team).roles
    holders = [
        slot
        for slot in team_slots(team)
        if roles[slot % 11] == "DM"
        and state.active[slot]
        and np.linalg.norm(state.pos[slot] - state.pos[carrier]) < SCREEN_REACH
    ]
    return holders[0] if holders else -1


def _press(
    state: MatchState, setup: MatchSetup, team: int, sign: int, targets: np.ndarray, speeds: np.ndarray
) -> None:
    """Decide who goes to the carrier.

    The nearest defender engages high up the pitch or after a pressing trigger, and otherwise
    contains goal-side. A carrier pinned near his own goal is trapped by two players; high-press
    sides add a passing-lane cover; and a holding midfielder steps out to meet a carrier driving
    centrally into the space in front of his back four.
    """
    carrier = state.owner
    if carrier < 0 or carrier in team_slots(team):
        return
    style = setup.team(team).style
    slots = np.array([s for s in team_slots(team)[1:] if state.active[s]])
    future = state.pos[carrier] + 0.3 * state.vel[carrier]
    reach = time_to_reach(
        state.pos[slots],
        state.vel[slots],
        future[None, :],
        state.traits["top_speed"][slots],
        state.traits["acceleration"][slots],
        state.traits["reaction_time"][slots],
    )[:, 0]
    order = slots[np.argsort(reach)]
    ball = to_attack_frame(future, sign)
    facing_back = float(state.vel[carrier, 0] * sign) > 0.5
    trigger = 15.0 * (state.heavy_touch_until > state.tick or facing_back or abs(ball[1] - CENTRE_Y) > 26)
    trapped = ball[0] > PITCH_LENGTH - TRAP_DEPTH
    engage = trapped or ball[0] + trigger >= 75.0 - 30.0 * style.press
    first = order[0]
    screen = _screening_midfielder(state, setup, team, ball, carrier)
    if screen >= 0:
        first, engage = screen, True
        order = np.array([screen, *[slot for slot in order if slot != screen]])
    top = state.traits["top_speed"]
    if engage:
        targets[first] = future
        speeds[first] = top[first] * (0.85 + 0.15 * style.press)
        if trapped and len(order) > 1:
            targets[order[1]] = future
            speeds[order[1]] = 0.9 * top[order[1]]
        elif style.press > 0.55 and len(order) > 1:
            mates = [s for s in team_slots(1 - team) if state.active[s] and s != carrier]
            nearest_mate = mates[int(np.argmin(np.linalg.norm(state.pos[mates] - future, axis=1)))]
            targets[order[1]] = 0.5 * (future + state.pos[nearest_mate])
            speeds[order[1]] = 0.8 * top[order[1]]
    else:
        own_goal = to_attack_frame(np.array([0.0, CENTRE_Y]), sign)
        towards_goal = own_goal - future
        targets[first] = future + 3.5 * towards_goal / max(float(np.linalg.norm(towards_goal)), 1e-6)
        speeds[first] = 0.7 * top[first]


def _box_runs(
    state: MatchState, setup: MatchSetup, team: int, sign: int, line: float, carrier_y: float
) -> None:
    """With a teammate in a crossing position, the forwards attack the near post, spot and far post."""
    side = np.sign(carrier_y - CENTRE_Y)
    zones = iter(((99.0, CENTRE_Y + 4.0 * side), (93.0, CENTRE_Y), (99.0, CENTRE_Y - 5.0 * side)))
    roles = setup.team(team).roles
    for index, slot in enumerate(team_slots(team)):
        if roles[index] in FORWARD_ROLES and slot != state.owner and state.active[slot]:
            zone = next(zones, None)
            if zone is None:
                return
            state.run_target[slot] = to_attack_frame(np.array([min(zone[0], line), zone[1]]), sign)
            state.run_until[slot] = state.tick + BOX_RUN_TICKS


def _runs(state: MatchState, setup: MatchSetup, tape: NoiseTape, team: int, sign: int, line: float) -> None:
    carrier = state.owner
    if carrier < 0 or carrier not in team_slots(team):
        return
    carrier_x, carrier_y = to_attack_frame(state.pos[carrier], sign)
    if carrier_x > 70.0 and abs(carrier_y - CENTRE_Y) > 12.0:
        _box_runs(state, setup, team, sign, line, carrier_y)
        return
    rivals = [s for s in team_slots(1 - team) if state.active[s]]
    pressure = float(np.min(np.linalg.norm(state.pos[rivals] - state.pos[carrier], axis=1)))
    if carrier_x < 30.0 or pressure < 4.0:
        return
    team_setup = setup.team(team)
    directness = team_setup.style.directness
    u = tape.uniform_all("run", state.tick)
    for index, slot in enumerate(team_slots(team)):
        if (
            team_setup.roles[index] not in FORWARD_ROLES
            or slot == carrier
            or state.run_until[slot] > state.tick
        ):
            continue
        x, y = to_attack_frame(state.pos[slot], sign)
        if not (line - 8.0 < x < line + MISTIMED_RUN) or u[slot, 0] > RUN_RATE * (0.4 + directness) * TICK:
            continue
        goal_ward = np.array([min(line + 14.0, PITCH_LENGTH - 4.0), y + 0.3 * (CENTRE_Y - y)])
        state.run_target[slot] = to_attack_frame(goal_ward, sign)
        state.run_until[slot] = state.tick + int(25 + 10 * u[slot, 1])


def offball_targets(state: MatchState, setup: MatchSetup, tape: NoiseTape) -> tuple[np.ndarray, np.ndarray]:
    """Targets and desired speeds for all 22 slots; also advances lapses, runs and drift."""
    _update_lapses(state, tape)
    noise = tape.normal_all("steer", state.tick)
    state.drift += -DRIFT_PULL * state.drift * TICK + DRIFT_SPREAD * np.sqrt(TICK) * noise
    perceived = state.ball_history[-1]
    targets = np.empty((22, 2))
    speeds = np.empty(22)
    for team in (0, 1):
        sign = attack_sign(team, state.period)
        slots = np.array(team_slots(team))
        in_possession = state.possession_team == team
        ball = to_attack_frame(perceived, sign)
        anchors = _anchors(setup.team(team), ball, in_possession)
        anchors[0] = _goalkeeper(ball, in_possession)
        if in_possession and state.phase == "play":
            line = offside_line(state, team, sign)
            limit = max(line, ball[0]) - OFFSIDE_DISCIPLINE
            anchors[1:, 0] = np.minimum(anchors[1:, 0], limit)
            _runs(state, setup, tape, team, sign, line)
        elif state.phase == "play":
            anchors = _mark(state, team, sign, anchors, ball)
        absolute = to_attack_frame(anchors, sign)
        targets[slots] = absolute
        targets[slots[1:]] += state.drift[slots[1:]]
        distance = np.linalg.norm(targets[slots] - state.pos[slots], axis=1)
        if state.phase == "play":
            cap = np.select([distance < 8.0, distance < 15.0], [JOG, RUN], RECOVERY)
        else:
            cap = np.full(len(slots), 3.0)
        speeds[slots] = np.minimum(WALK_GAIN * distance, cap)
        keeper = slots[0]
        speeds[keeper] = min(KEEPER_URGENCY * distance[0], state.traits["top_speed"][keeper])
        running = slots[state.run_until[slots] > state.tick]
        targets[running] = state.run_target[running]
        speeds[running] = 0.95 * state.traits["top_speed"][running]
        if state.phase == "play":
            _press(state, setup, team, sign, targets, speeds)
    return targets, speeds
