"""The 10 Hz match loop: periods, added time, fatigue and the dispatch between phases."""

import sys
from dataclasses import dataclass

import numpy as np

from frontroom_engine.league.model import League
from frontroom_engine.sim.core import TICKS_PER_MINUTE, Simulator
from frontroom_engine.sim.flight import flight_tick
from frontroom_engine.sim.motion import steer
from frontroom_engine.sim.noise import NoiseTape
from frontroom_engine.sim.offball import offball_targets
from frontroom_engine.sim.onball import carrier_tick
from frontroom_engine.sim.possession import fail_pass
from frontroom_engine.sim.recorder import Recording
from frontroom_engine.sim.referee import added_minutes, plan_substitutions, substitutions_due
from frontroom_engine.sim.restarts import dead_tick, place_for_kick_off
from frontroom_engine.sim.setup import MatchSetup, make_setup
from frontroom_engine.sim.state import MatchState, initial_state

HALF_TICKS = 45 * TICKS_PER_MINUTE
URGENT = 0.95
FATIGUE_DRAIN = 0.0025
FATIGUE_BASELINE = 0.000005
FATIGUE_RECOVERY = 0.0004
FINISH_GRACE_TICKS = 300
SAFE_ZONE = 30.0
BLOCKED_CARRY_SPEED = 1.2
BLOCK_DEPTH = 1.5
BLOCK_WIDTH = 0.9


@dataclass(frozen=True)
class MatchResult:
    setup: MatchSetup
    state: MatchState
    recording: Recording
    branches: tuple[tuple[int, int], ...] = ()
    """Noise-tape branch points used to steer the match; empty for an unsteered match."""


def effective_top_speed(state: MatchState) -> np.ndarray:
    return state.traits["top_speed"] * (0.88 + 0.12 * state.energy)


def _play_tick(sim: Simulator) -> None:
    s = sim.state
    targets, speeds = offball_targets(s, sim.setup, sim.tape)
    top = effective_top_speed(s)
    for slot, target in s.intercept_targets.items():
        targets[slot] = target
        speeds[slot] = URGENT * top[slot]
    if s.owner >= 0:
        targets[s.owner] = s.carry_target
        speeds[s.owner] = min(s.carry_speed, _blocked_speed(sim, s.owner))
    inactive = ~s.active
    targets[inactive], speeds[inactive] = s.pos[inactive], 0.0
    s.pos, s.vel = steer(s.pos, s.vel, targets, speeds, top, s.traits["acceleration"])
    if s.owner >= 0:
        carrier_tick(sim)
    else:
        flight_tick(sim)


def _blocked_speed(sim: Simulator, carrier: int) -> float:
    """A carrier cannot run through a defender standing in his path; he slows to go round him."""
    s = sim.state
    heading = s.carry_target - s.pos[carrier]
    length = float(np.linalg.norm(heading))
    if length < 1e-6:
        return BLOCKED_CARRY_SPEED
    rivals = sim.active_slots(1 - carrier // 11)
    offsets = s.pos[rivals] - s.pos[carrier]
    ahead = offsets @ (heading / length)
    across = np.abs(offsets @ (np.array([-heading[1], heading[0]]) / length))
    blocking = (ahead > 0.0) & (ahead < BLOCK_DEPTH) & (across < BLOCK_WIDTH)
    return BLOCKED_CARRY_SPEED if blocking.any() else np.inf


def _tire(state: MatchState) -> None:
    speed = np.linalg.norm(state.vel, axis=1)
    effort = (speed / state.traits["top_speed"]) ** 3
    drain = (FATIGUE_DRAIN * effort + FATIGUE_BASELINE) * (1.4 - state.traits["stamina"])
    state.energy = np.clip(state.energy - drain + FATIGUE_RECOVERY * (speed < 2.0), 0.5, 1.0)


def _start_period(sim: Simulator, period: int) -> None:
    s = sim.state
    s.period = period
    s.period_start_tick = s.tick
    s.period_end_tick = sys.maxsize
    place_for_kick_off(sim, kicking=0 if period == 1 else 1)


def _clock(sim: Simulator) -> None:
    s = sim.state
    if s.tick - s.period_start_tick == HALF_TICKS:
        s.period_end_tick = s.tick + added_minutes(sim) * TICKS_PER_MINUTE
    if s.tick < s.period_end_tick:
        return
    quiet = s.phase == "dead" or abs(s.ball_pos[0] - 52.5) < SAFE_ZONE
    if not quiet and s.tick < s.period_end_tick + FINISH_GRACE_TICKS:
        return
    fail_pass(sim, s.ball_pos[:2])
    if s.period == 1:
        _start_period(sim, 2)
    else:
        sim.finished = True


def step(sim: Simulator) -> None:
    s = sim.state
    was_live = s.phase == "play"
    if was_live:
        _play_tick(sim)
    else:
        dead_tick(sim)
    if was_live and s.phase == "dead":
        substitutions_due(sim)
    _tire(s)
    s.ball_history = np.vstack([s.ball_pos[:2], s.ball_history[:-1]])
    sim.recording.capture(s)
    s.tick += 1
    _clock(sim)


def run(sim: Simulator, until_tick: int | None = None) -> None:
    while not sim.finished and (until_tick is None or sim.state.tick < until_tick):
        step(sim)


def run_to_minute(sim: Simulator, minute: float) -> None:
    """Run until the broadcast clock shows `minute` (second-half minutes count from 45)."""
    while not sim.finished and ((sim.state.period == 1 and minute > 45) or sim.minute < minute):
        step(sim)


def create_simulator(setup: MatchSetup, tape: NoiseTape | None = None) -> Simulator:
    state = initial_state(setup.home.club.starting_eleven(), setup.away.club.starting_eleven())
    sim = Simulator(setup, tape or NoiseTape(setup.seed), state, Recording())
    plan_substitutions(sim)
    _start_period(sim, 1)
    return sim


def finish(sim: Simulator) -> MatchResult:
    run(sim)
    return MatchResult(sim.setup, sim.state, sim.recording, sim.tape.branches)


def simulate_match(league: League, home: str, away: str, seed: int) -> MatchResult:
    """Simulate a full match between the clubs with short codes `home` and `away`."""
    return finish(create_simulator(make_setup(league, home, away, seed)))
