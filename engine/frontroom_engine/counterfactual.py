"""Counterfactual replays: restore a match at a decision and play it out with a different choice.

A match is replayed once from kick-off on its own noise tape, and the state is cloned at every
tick of interest. Each counterfactual starts from such a clone, forces the carrier's decision
to a given option (or withholds a player from a ball he won), and runs for a fixed horizon.
With `salt=None` the run keeps the factual noise everywhere, so forcing the option that was
actually chosen reproduces the match exactly. With a salt, everything downstream of the
decision is resampled while the situation at the moment of the decision stays identical;
using the same salt for every option pairs the comparison.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from frontroom_engine.sim.core import Simulator
from frontroom_engine.sim.match import create_simulator, run
from frontroom_engine.sim.noise import NoiseTape
from frontroom_engine.sim.recorder import Recording
from frontroom_engine.sim.records import ShotTruth
from frontroom_engine.sim.setup import MatchSetup
from frontroom_engine.sim.state import MatchState

HORIZON_TICKS = 150
"""15 seconds: the fixed horizon over which a decision's consequences are counted."""
WITHHOLD_TICKS = 10
"""How long a withheld player is kept off the ball when a regain is removed."""


@dataclass(frozen=True)
class Checkpoint:
    tick: int
    state: MatchState
    tape: NoiseTape


def replay_checkpoints(
    setup: MatchSetup, branches: tuple[tuple[int, int], ...], ticks: Iterable[int]
) -> dict[int, Checkpoint]:
    """Replay the match from kick-off and clone the state at the start of each requested tick."""
    sim = create_simulator(setup, NoiseTape(setup.seed, branches))
    checkpoints: dict[int, Checkpoint] = {}
    for tick in sorted(set(ticks)):
        run(sim, until_tick=tick)
        checkpoints[tick] = Checkpoint(tick, sim.state.clone(), sim.tape)
    return checkpoints


def net_xg(shots: Sequence[ShotTruth], team: int) -> float:
    """Physical xG created by `team` minus the xG it conceded."""
    return sum(shot.xg if shot.team == team else -shot.xg for shot in shots)


def rollout(
    setup: MatchSetup,
    checkpoint: Checkpoint,
    slot: int,
    option: int | None = None,
    *,
    withhold: bool = False,
    salt: int | None = None,
    horizon_ticks: int = HORIZON_TICKS,
    recording: Recording | None = None,
) -> Simulator:
    """Run one counterfactual from `checkpoint` and return the simulator at the horizon."""
    tape = (
        checkpoint.tape if salt is None else checkpoint.tape.resampled_after_decision(checkpoint.tick, salt)
    )
    sim = Simulator(setup, tape, checkpoint.state.clone(), recording or Recording())
    if option is not None:
        sim.forced_choice = (checkpoint.tick, slot, option)
    if withhold:
        sim.withheld = (slot, checkpoint.tick, checkpoint.tick + WITHHOLD_TICKS)
    run(sim, until_tick=checkpoint.tick + horizon_ticks)
    return sim


def run_alternative(
    setup: MatchSetup,
    checkpoint: Checkpoint,
    slot: int,
    option: int | None = None,
    *,
    withhold: bool = False,
    salt: int | None = None,
    horizon_ticks: int = HORIZON_TICKS,
    recording: Recording | None = None,
) -> float | None:
    """Net xG for the slot's team over the horizon, or None if the forced decision never came up."""
    shots_before = len(checkpoint.state.shots)
    decisions_before = len(checkpoint.state.decisions)
    sim = rollout(
        setup,
        checkpoint,
        slot,
        option,
        withhold=withhold,
        salt=salt,
        horizon_ticks=horizon_ticks,
        recording=recording,
    )
    if option is not None:
        player = checkpoint.state.player_id(slot)
        decided = sim.state.decisions[decisions_before:]
        if not any(
            d.tick == checkpoint.tick and d.player_id == player and d.chosen == option for d in decided
        ):
            return None
    return net_xg(sim.state.shots[shots_before:], slot // 11)
