"""The options a ball carrier weighs, and the hand-built utility of each.

Utility = perceived success x value if it works - perceived failure x cost if it does not.
Perceived success for a pass comes from time-to-intercept margins against the opponents the
carrier can actually see (scan radius and facing); the real outcome is decided later by
physics. Values come from `geometry.threat`, a hand-built potential, never from VAEP or xT.
"""

from dataclasses import dataclass

import numpy as np

from frontroom_engine.pitch import CENTRE_Y, PITCH_LENGTH
from frontroom_engine.sim.ball import (
    GRAVITY,
    ROLL_DAMPING,
    ROLL_DECEL,
    ground_flight_time,
    ground_launch_speed,
    lofted_launch,
)
from frontroom_engine.sim.geometry import (
    goal_angle,
    goal_distance,
    inside_pitch,
    threat,
)
from frontroom_engine.sim.perception import CarrierView, build_view, loss_if_lost, sigmoid
from frontroom_engine.sim.setup import MatchSetup
from frontroom_engine.sim.state import MatchState

MAX_OPTIONS = 16
PASS_CANDIDATES = 7
PATH_SAMPLES = 12
SHOT_VALUE = 2.8
"""How much a goal is worth relative to the 0..1 pitch-value scale of `threat`."""
SHOT_RANGE = 33.0
CARRY_LENGTH = 6.0
CONTROL_REACH = 1.0
PLAYABLE_HEIGHT = 2.3
LOFT_DISTANCE = 32.0
"""Passes longer than this are played in the air."""
"""A player can play a ground ball passing within about a metre of him."""
LANDING_SAMPLES = 1
"""Path samples at the receiving end, judged as a race with the receiver rather than with the ball."""
CROWD_RADIUS = 4.0
CROWD_PENALTY = 0.1
CARRY_TIME_COST = 0.04
"""Carrying gives the defence time to reorganise; faster-tempo sides feel this more."""
CROSS_ANGLE = 22.0
CROSS_ZONES = ((94.0, -1.0), (99.0, -6.0))
"""Penalty spot and far post, as (x, lateral offset towards the crosser's side).

Aimed across the face of goal, an unmet cross runs on past the far post rather than into the net."""
LONG_BALL_ROLES = ("ST", "RW", "LW")
"""Players a passer looks for by habit, whether or not he has just scanned them."""


@dataclass(frozen=True)
class Option:
    kind: str
    target_slot: int
    end: np.ndarray
    """Attacking-frame end point; the executor converts it back to pitch coordinates."""
    speed: float
    loft: float
    utility: float
    success: float


def ground_arrival_speed(distance: np.ndarray, tempo: float) -> np.ndarray:
    """How hard a ground pass is struck, expressed as the speed it should still have on arrival."""
    return np.clip(6.0 + 0.25 * distance, 6.0, 15.0) * (0.9 + 0.2 * tempo)


def _pass_paths(
    start: np.ndarray, ends: np.ndarray, lofted: np.ndarray, tempo: float
) -> tuple[np.ndarray, ...]:
    """Sampled ball positions, times and interceptable mask along each candidate pass."""
    offsets = ends - start
    distance = np.linalg.norm(offsets, axis=1)
    direction = offsets / np.maximum(distance, 1e-6)[:, None]
    arrival = ground_arrival_speed(distance, tempo)
    speed = ground_launch_speed(distance, arrival)
    duration = ground_flight_time(speed, arrival)
    fractions = np.linspace(0.0, 1.0, PATH_SAMPLES)
    times = duration[:, None] * fractions[None, :]
    k = speed[:, None] + ROLL_DECEL / ROLL_DAMPING
    travelled = k * (1 - np.exp(-ROLL_DAMPING * times)) / ROLL_DAMPING - ROLL_DECEL / ROLL_DAMPING * times
    reachable = np.ones_like(times, dtype=bool)
    for i in np.flatnonzero(lofted):
        loft_speed, loft_time = lofted_launch(float(distance[i]), loft_angle(float(distance[i])))
        speed[i], times[i] = loft_speed, loft_time * fractions
        travelled[i] = distance[i] * fractions
        height = (
            loft_speed * np.sin(np.radians(loft_angle(float(distance[i])))) * times[i]
            - 0.5 * GRAVITY * times[i] ** 2
        )
        reachable[i] = height < PLAYABLE_HEIGHT
    points = start + direction[:, None, :] * travelled[:, :, None]
    return points, times, reachable, speed


def loft_angle(distance: float) -> float:
    return float(np.clip(22.0 + 0.35 * (distance - 30.0), 18.0, 42.0))


def _pass_options(view: CarrierView, setup: MatchSetup) -> list[Option]:
    state, style = view.state, setup.team(view.team).style
    lead = np.clip(np.linalg.norm(view.mate_pos - view.pos, axis=1) / 15.0, 0.0, 0.8)
    ends = view.mate_pos + view.mate_vel * lead[:, None]
    distance = np.linalg.norm(ends - view.pos, axis=1)
    scan = state.traits["scan_radius"][view.carrier]
    ahead = (ends - view.pos) @ view.facing > 0.5 * distance
    roles = setup.team(view.team).roles
    habitual = np.array([roles[slot % 11] in LONG_BALL_ROLES for slot in view.mates])
    visible = (distance < scan) | (ahead & (distance < 1.5 * scan)) | habitual
    is_keeper = np.isin(view.mates, (0, 11))
    usable = visible & (distance > 4.0) & (distance < 65.0) & (~is_keeper | (view.pos[0] < 35.0))
    candidates = np.flatnonzero(usable)
    if candidates.size == 0:
        return []
    candidates = candidates[np.argsort(-threat(ends[candidates, 0], ends[candidates, 1]))][:PASS_CANDIDATES]
    lofted = distance[candidates] > LOFT_DISTANCE
    points, times, reachable, speeds = _pass_paths(view.pos, ends[candidates], lofted, style.tempo)
    n, k = points.shape[:2]
    rival_times = view.rival_reach(points.reshape(-1, 2), reach=CONTROL_REACH).reshape(len(view.rivals), n, k)
    lane = reachable.copy()
    lane[:, -LANDING_SAMPLES:] = False
    lane_margin = np.where(lane[None], rival_times - times[None], np.inf).min(axis=(0, 2))
    end_rival = rival_times[:, :, -1].min(axis=0)
    noise = state.traits["pass_noise"][view.carrier]
    options = []
    for row, index in enumerate(candidates):
        end = ends[index]
        arrival = times[row, -1]
        receiver_time = view.mate_reach(index, end)
        contested_from = receiver_time if lofted[row] else max(arrival, receiver_time)
        end_margin = end_rival[row] - contested_from
        success = float(
            sigmoid((lane_margin[row] - 0.1) / 0.15)
            * sigmoid((end_margin + 0.3) / 0.25)
            * sigmoid((arrival + 0.6 - receiver_time) / 0.25)
            * np.exp(-distance[index] * noise / 6.0)
            * (0.85 if lofted[row] else 1.0)
        )
        space = np.clip(np.min(np.linalg.norm(view.rival_pos - end, axis=1)) / 10.0, 0.0, 1.0)
        bypassed = np.sum((view.rival_pos[:, 0] > view.pos[0]) & (view.rival_pos[:, 0] < end[0]))
        progress = np.clip((end[0] - view.pos[0]) / 20.0, -1.0, 2.0)
        gain = (
            float(threat(end[0], end[1]))
            + 0.08 * space
            + 0.02 * bypassed
            + 0.06 * style.directness * progress
        )
        utility = success * gain - (1.0 - success) * float(loss_if_lost(end, style.risk)[0])
        loft = loft_angle(float(distance[index])) if lofted[row] else 0.0
        kind = "long" if lofted[row] else "pass"
        options.append(Option(kind, int(view.mates[index]), end, float(speeds[row]), loft, utility, success))
    return options


def _shot_option(view: CarrierView, setup: MatchSetup) -> list[Option]:
    x, y = view.pos
    distance = float(goal_distance(x, y))
    if distance > SHOT_RANGE or x < PITCH_LENGTH / 2:
        return []
    angle = float(goal_angle(np.array(x), np.array(y)))
    perceived = float(sigmoid(-0.5 - 0.105 * distance + 1.4 * angle - 1.0 * view.pressure))
    risk = setup.team(view.team).style.risk
    utility = SHOT_VALUE * perceived * (1.0 + 0.4 * (risk - 0.5)) + 0.08 * (1.0 - perceived)
    return [Option("shot", -1, np.array([PITCH_LENGTH, CENTRE_Y]), 0.0, 0.0, utility, perceived)]


def _cross_options(view: CarrierView, setup: MatchSetup) -> list[Option]:
    x, y = view.pos
    if x < 80.0 or abs(y - CENTRE_Y) < 12.0:
        return []
    side = np.sign(y - CENTRE_Y)
    style = setup.team(view.team).style
    options = []
    for zone_x, offset in CROSS_ZONES:
        zone = np.array([zone_x, CENTRE_Y + offset * side])
        attackers = np.sum(np.linalg.norm(view.mate_pos - zone, axis=1) < 6.0)
        defenders = np.sum(np.linalg.norm(view.rival_pos - zone, axis=1) < 6.0)
        success = float(np.clip(0.3 + 0.12 * attackers - 0.06 * defenders, 0.05, 0.6))
        value = float(threat(zone[0], zone[1])) + 0.25 + 0.1 * style.width
        utility = success * value - (1.0 - success) * 0.3 * float(loss_if_lost(zone, style.risk)[0])
        distance = float(np.linalg.norm(zone - view.pos))
        options.append(
            Option("cross", -1, zone, lofted_launch(distance, CROSS_ANGLE)[0], CROSS_ANGLE, utility, success)
        )
    return options


def _carry_options(view: CarrierView, setup: MatchSetup) -> list[Option]:
    state, style = view.state, setup.team(view.team).style
    carrier = view.carrier
    speed = 0.7 * state.traits["top_speed"][carrier]
    angles = np.radians([0.0, 35.0, -35.0])
    ends = view.pos + CARRY_LENGTH * np.stack([np.cos(angles), np.sin(angles)], axis=1)
    ends = ends[inside_pitch(ends, margin=1.0)]
    if len(ends) == 0:
        return []
    fractions = np.linspace(0.25, 1.0, 4)
    path = view.pos + (ends - view.pos)[:, None, :] * fractions[None, :, None]
    rival_times = view.rival_reach(path.reshape(-1, 2), only_seen=False).min(axis=0).reshape(len(ends), -1)
    margin = (rival_times - fractions * CARRY_LENGTH / speed).min(axis=1)
    crowd = np.sum(
        np.linalg.norm(view.rival_pos[None, :, :] - ends[:, None, :], axis=2) < CROWD_RADIUS, axis=1
    )
    caught = (1.0 - sigmoid(margin / 0.3)) * (
        0.95 - 0.35 * state.traits["dribbling"][carrier]
    ) + CROWD_PENALTY * crowd
    success = np.clip(1.0 - caught, 0.02, 1.0)
    loss = float(loss_if_lost(view.pos, style.risk)[0])
    time_cost = CARRY_TIME_COST * (0.5 + style.tempo)
    utility = success * threat(ends[:, 0], ends[:, 1]) - (1 - success) * 0.8 * loss - time_cost
    return [
        Option("carry", -1, e, speed, 0.0, float(u), float(s))
        for e, u, s in zip(ends, utility, success, strict=True)
    ]


def _take_on_option(view: CarrierView, setup: MatchSetup) -> list[Option]:
    offset = view.rival_pos[view.nearest_rival] - view.pos
    if np.linalg.norm(offset) > 5.0 or offset[0] < -1.0:
        return []
    state, style = view.state, setup.team(view.team).style
    defender = view.rivals[view.nearest_rival]
    side = 1.0 if view.pos[1] < CENTRE_Y else -1.0
    end = view.rival_pos[view.nearest_rival] + np.array([3.0, 1.5 * side])
    duel = state.traits["dribbling"][view.carrier] - state.traits["tackling"][defender]
    success = float(np.clip(0.45 + 0.5 * duel, 0.1, 0.85))
    gain = float(threat(end[0], end[1])) + 0.05
    utility = success * gain - (1 - success) * float(loss_if_lost(view.pos, style.risk)[0])
    speed = 0.8 * state.traits["top_speed"][view.carrier]
    return [Option("take_on", int(defender), end, speed, 0.0, utility, success)]


def _hold_and_clear(view: CarrierView, setup: MatchSetup) -> list[Option]:
    style = setup.team(view.team).style
    away = view.pos - view.rival_pos[view.nearest_rival]
    end = view.pos + 1.5 * away / max(float(np.linalg.norm(away)), 1e-6)
    keep = 1.0 - 0.7 * view.pressure
    loss = float(loss_if_lost(view.pos, style.risk)[0])
    hold = keep * float(threat(view.pos[0], view.pos[1])) - (1 - keep) * loss - 0.03
    options = [Option("hold", -1, end, 1.5, 0.0, hold, keep)]
    if view.pos[0] < 30.0 and view.pressure > 0.3:
        side = 1.0 if view.pos[1] > CENTRE_Y else -1.0
        target = np.array([view.pos[0] + 40.0, CENTRE_Y + 22.0 * side])
        utility = 0.12 + 0.2 * view.pressure + 0.1 * (1.0 - style.risk)
        options.append(Option("clear", -1, target, lofted_launch(45.0, 35.0)[0], 35.0, utility, 0.4))
    return options


def enumerate_options(state: MatchState, setup: MatchSetup, carrier: int) -> list[Option]:
    view = build_view(state, carrier)
    options = (
        _pass_options(view, setup)
        + _shot_option(view, setup)
        + _cross_options(view, setup)
        + _carry_options(view, setup)
        + _take_on_option(view, setup)
        + _hold_and_clear(view, setup)
    )
    return options[:MAX_OPTIONS]
