import numpy as np

from frontroom_engine.extract.events import extract_events
from frontroom_engine.league import League
from frontroom_engine.sim.match import create_simulator, run
from frontroom_engine.sim.noise import NoiseTape
from frontroom_engine.sim.setup import make_setup

FIVE_MINUTES = 3000


def _run(league: League, seed: int, tape: NoiseTape | None = None, ticks: int = FIVE_MINUTES):
    sim = create_simulator(make_setup(league, "KES", "ASH", seed), tape)
    run(sim, until_tick=ticks)
    return sim


def test_same_seed_gives_identical_tracking_and_feed(league: League) -> None:
    first, second = _run(league, 3), _run(league, 3)
    n = first.recording.length
    np.testing.assert_array_equal(first.recording.pos[:n], second.recording.pos[:n])
    np.testing.assert_array_equal(first.recording.ball[:n], second.recording.ball[:n])
    feed_a = extract_events("m", 3, first.state.actions).events
    feed_b = extract_events("m", 3, second.state.actions).events
    assert feed_a == feed_b


def test_different_seeds_give_different_matches(league: League) -> None:
    first, second = _run(league, 3), _run(league, 4)
    assert not np.array_equal(first.recording.ball[:FIVE_MINUTES], second.recording.ball[:FIVE_MINUTES])


def test_a_branch_replays_the_past_exactly_and_then_diverges(league: League) -> None:
    """The keyed tape is what lets counterfactual and steered runs stay paired up to the branch."""
    branch_tick = 1500
    plain = _run(league, 5)
    branched = _run(league, 5, NoiseTape(5).branched(branch_tick, salt=99))
    np.testing.assert_array_equal(plain.recording.pos[:branch_tick], branched.recording.pos[:branch_tick])
    assert not np.array_equal(
        plain.recording.pos[branch_tick:FIVE_MINUTES], branched.recording.pos[branch_tick:FIVE_MINUTES]
    )
