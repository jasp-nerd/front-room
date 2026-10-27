"""Physical sanity of the 25 Hz tracking: nobody teleports, nobody outruns a sprinter."""

import numpy as np
import pytest

from frontroom_engine.extract.tracking import FRAME_RATE, Tracking, resample
from frontroom_engine.sim.match import MatchResult

MAX_PLAYER_SPEED = 9.6
MAX_BALL_SPEED = 40.0


@pytest.fixture(scope="module")
def tracking(match: MatchResult) -> Tracking:
    return resample(match.recording)


def test_reported_speeds_stay_within_human_limits(tracking: Tracking) -> None:
    on_pitch = tracking.roster >= 0
    assert tracking.speed[on_pitch].max() <= MAX_PLAYER_SPEED
    assert np.percentile(tracking.speed[on_pitch], 99.9) > 6.0


def test_no_player_teleports_between_frames(tracking: Tracking) -> None:
    same_player = (tracking.roster[1:] == tracking.roster[:-1]) & (tracking.roster[1:] >= 0)
    same_period = (tracking.period[1:] == tracking.period[:-1])[:, None]
    step = np.linalg.norm(np.diff(tracking.pos, axis=0), axis=2)
    assert step[same_player & same_period].max() <= MAX_PLAYER_SPEED / FRAME_RATE + 1e-3


def test_ball_never_flies_faster_than_a_hard_shot(tracking: Tracking) -> None:
    live = tracking.alive[1:] & tracking.alive[:-1] & (tracking.period[1:] == tracking.period[:-1])
    speed = np.linalg.norm(np.diff(tracking.ball, axis=0), axis=1) * FRAME_RATE
    assert speed[live].max() <= MAX_BALL_SPEED
    assert tracking.ball[:, 2].min() >= 0.0


def test_twenty_two_players_or_fewer_and_never_two_slots_for_one_player(tracking: Tracking) -> None:
    for row in tracking.roster[:: FRAME_RATE * 30]:
        present = row[row >= 0]
        assert 18 <= len(present) <= 22
        assert len(set(present.tolist())) == len(present)


def test_the_ball_is_in_play_for_a_realistic_share_of_the_match(tracking: Tracking) -> None:
    assert 0.45 < tracking.alive.mean() < 0.75
    halves = [np.sum(tracking.period == p) / FRAME_RATE / 60 for p in (1, 2)]
    assert all(45.0 <= minutes <= 54.0 for minutes in halves)
