"""Putting the ball in motion and sending players after it.

Pass success is not decided when the pass is struck. The ball follows its physical path, and
the intended receiver and the opponents who can get there in time (by `time_to_reach`) run to
their earliest reachable point on it. Who actually gets the ball is settled in flight.
"""

import numpy as np

from frontroom_engine.pitch import PITCH_LENGTH, in_penalty_area
from frontroom_engine.sim.ball import TICK, integrate
from frontroom_engine.sim.core import Simulator, point
from frontroom_engine.sim.motion import time_to_reach
from frontroom_engine.sim.offball import offside_line
from frontroom_engine.sim.state import PendingPass

PATH_STEPS = 60
KICKER_COOLDOWN = 3
PLAYABLE_HEIGHT = 2.3
KEEPER_PLAYABLE_HEIGHT = 2.8
KEEPER_MARGIN_TICKS = 3
"""A keeper leaves his line only for a ball he will reach clearly before any attacker."""
CONTROL_REACH = 1.0
NO_OFFSIDE_RESTARTS = ("throw_in", "corner", "goal_kick")


def launch(sim: Simulator, velocity: np.ndarray, kicker: int, receiver: int = -1) -> None:
    s = sim.state
    s.owner = -1
    s.take_on = None
    s.last_touch = kicker
    s.kicker_cooldown_until = s.tick + KICKER_COOLDOWN
    s.launch_tick = s.tick
    s.ball_vel = np.asarray(velocity, dtype=float)
    path, path_vel = integrate(s.ball_pos, s.ball_vel, PATH_STEPS)
    s.ball_path, s.ball_path_vel = path[:, 0], path_vel[:, 0]
    assign_chasers(sim, receiver, kicker)


def assign_chasers(sim: Simulator, receiver: int, kicker: int) -> None:
    """Send the receiver and the best-placed opponents to their earliest reachable points on the path."""
    s = sim.state
    points = s.ball_path[:, :2]
    times = (np.arange(len(points)) + 1) * TICK
    slots = np.array([slot for slot in range(22) if s.active[slot] and slot != kicker])
    t = s.traits
    reach = time_to_reach(
        s.pos[slots],
        s.vel[slots],
        points,
        t["top_speed"][slots],
        t["acceleration"][slots],
        t["reaction_time"][slots],
        CONTROL_REACH,
    )
    height_limit = np.where(slots % 11 == 0, KEEPER_PLAYABLE_HEIGHT, PLAYABLE_HEIGHT)[:, None]
    feasible = (reach <= times + 0.15) & (s.ball_path[None, :, 2] < height_limit)
    last = len(points) - 1
    first = np.where(feasible.any(axis=1), np.argmax(feasible, axis=1), last + 1)
    passing_team = kicker // 11 if kicker >= 0 else -1
    keeper_rows = np.flatnonzero(slots % 11 == 0)
    targets: dict[int, tuple[float, float]] = {}
    for team in (0, 1):
        if team == passing_team and receiver >= 0:
            row = int(np.flatnonzero(slots == receiver)[0])
            targets[receiver] = point(points[min(first[row], last)])
            continue
        rows = np.flatnonzero((slots // 11 == team) & (slots % 11 != 0))
        if rows.size == 0:
            continue
        chasers = 1 if team == passing_team else 2
        ranked = rows[np.argsort(first[rows], kind="stable")]
        chosen = [row for row in ranked[:chasers] if first[row] <= last] or [
            rows[int(np.argmin(reach[rows, -1]))]
        ]
        for row in chosen:
            targets[int(slots[row])] = point(points[min(first[row], last)])
    for row in keeper_rows:
        keeper = int(slots[row])
        attackers = (slots // 11 != keeper // 11) & (slots % 11 != 0)
        attackers_first = int(first[attackers].min()) if attackers.any() else last + 1
        clearly_first = first[row] + KEEPER_MARGIN_TICKS <= attackers_first
        if first[row] <= last and clearly_first and _in_own_box(sim, keeper, points[first[row]]):
            targets[keeper] = point(points[first[row]])
    s.intercept_targets = targets


def _in_own_box(sim: Simulator, keeper: int, xy: np.ndarray) -> bool:
    own_goal_x = 0.0 if sim.sign(keeper // 11) > 0 else PITCH_LENGTH
    return in_penalty_area(float(xy[0]), float(xy[1]), own_goal_x)


def offside_margins(sim: Simulator, passer: int) -> dict[int, float]:
    """Teammates in an offside position at the moment of the pass, with how far beyond the line they are."""
    s = sim.state
    team = passer // 11
    sign = sim.sign(team)
    line = max(offside_line(s, team, sign), float(sim.relative(s.ball_pos[:2], team)[0]))
    margins = {}
    for slot in sim.active_slots(team):
        x = float(sim.relative(s.pos[slot], team)[0])
        if slot != passer and x > line:
            margins[slot] = x - line
    return margins


def start_pass(
    sim: Simulator,
    passer: int,
    receiver: int,
    action_id: int,
    kind: str,
    *,
    lofted: bool,
    body_part: str = "foot",
) -> None:
    """Remember the pass so it can be logged, with its real outcome, once the ball is played again."""
    s = sim.state
    offside = {} if kind in NO_OFFSIDE_RESTARTS else offside_margins(sim, passer)
    s.pending_pass = PendingPass(
        action_id, kind, passer, receiver, point(s.ball_pos[:2]), s.tick, lofted, body_part, offside
    )
