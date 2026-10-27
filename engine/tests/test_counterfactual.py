import numpy as np
import pytest

from frontroom_engine.counterfactual import Checkpoint, replay_checkpoints, rollout
from frontroom_engine.extract.events import extract_events
from frontroom_engine.oracle import attribute_goals, verdict
from frontroom_engine.sim.match import MatchResult
from frontroom_engine.sim.records import Decision

HORIZON = 300


@pytest.fixture(scope="module")
def decision(match: MatchResult) -> Decision:
    return next(d for d in match.state.decisions[400:] if len(d.options) > 2)


@pytest.fixture(scope="module")
def checkpoint(match: MatchResult, decision: Decision) -> Checkpoint:
    return replay_checkpoints(match.setup, match.branches, [decision.tick])[decision.tick]


def _slot(checkpoint: Checkpoint, player_id: str) -> int:
    return next(i for i, p in enumerate(checkpoint.state.players) if p is not None and p.id == player_id)


def test_forcing_the_factual_choice_reproduces_the_match_exactly(
    match: MatchResult, decision: Decision, checkpoint: Checkpoint
) -> None:
    sim = rollout(
        match.setup, checkpoint, _slot(checkpoint, decision.player_id), decision.chosen, horizon_ticks=HORIZON
    )
    window = slice(decision.tick, decision.tick + HORIZON)
    np.testing.assert_array_equal(sim.recording.pos[window], match.recording.pos[window])
    np.testing.assert_array_equal(sim.recording.ball[window], match.recording.ball[window])
    factual = [a for a in match.state.actions if a.tick < decision.tick + HORIZON - 50]
    assert [a for a in sim.state.actions if a.tick < decision.tick + HORIZON - 50] == factual


def test_forcing_another_option_changes_what_happens(
    match: MatchResult, decision: Decision, checkpoint: Checkpoint
) -> None:
    other = (decision.chosen + 1) % len(decision.options)
    sim = rollout(
        match.setup, checkpoint, _slot(checkpoint, decision.player_id), other, horizon_ticks=HORIZON
    )
    window = slice(decision.tick + 1, decision.tick + HORIZON)
    assert not np.array_equal(sim.recording.ball[window], match.recording.ball[window])


def test_resampled_futures_start_from_the_same_decision(
    decision: Decision, checkpoint: Checkpoint, match: MatchResult
) -> None:
    """Fresh noise downstream of the decision must not change the situation the player decided in."""
    slot = _slot(checkpoint, decision.player_id)
    for salt in (1, 2):
        sim = rollout(match.setup, checkpoint, slot, decision.chosen, salt=salt, horizon_ticks=5)
        replayed = next(
            d for d in sim.state.decisions if d.tick == decision.tick and d.player_id == decision.player_id
        )
        assert replayed.options == decision.options


def test_verdict_needs_a_clear_and_large_enough_winner() -> None:
    clear = [
        {"eventId": "a", "tau": 0.08, "low": 0.05, "high": 0.11},
        {"eventId": "b", "tau": 0.01, "low": -0.01, "high": 0.03},
    ]
    overlapping = [
        {"eventId": "a", "tau": 0.08, "low": 0.02, "high": 0.11},
        {"eventId": "b", "tau": 0.04, "low": 0.0, "high": 0.06},
    ]
    small = [{"eventId": "a", "tau": 0.03, "low": 0.02, "high": 0.04}]
    assert verdict(clear) == {"label": "decisive", "decisiveEventId": "a"}
    assert verdict(overlapping)["label"] == "shared"
    assert verdict(small)["label"] == "shared"


def test_every_goal_gets_feed_linked_attributions(match: MatchResult) -> None:
    feed = extract_events(match.setup.match_id, match.setup.seed, match.state.actions)
    records = attribute_goals(match, feed, samples=2)
    event_ids = {e["id"] for e in feed.events}
    assert records and sum(match.state.score) >= len(records)
    for record in records:
        assert record["goalEventId"] in event_ids and record["shotEventId"] in event_ids
        assert record["actions"]
        for row in record["actions"]:
            assert row["eventId"] in event_ids
            assert row["low"] <= row["tau"] <= row["high"]
