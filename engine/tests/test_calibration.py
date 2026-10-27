import numpy as np

from frontroom_engine.calibration.definitions import count_sprints, pass_band, speed_band_shares
from frontroom_engine.calibration.reference import load_reference
from frontroom_engine.calibration.scorecard import CHECKS, evaluate, markdown, scorecard


def test_sprints_need_a_full_second_above_sprint_speed() -> None:
    speeds = np.array([20.0] * 10 + [26.0] * 25 + [20.0] * 5 + [26.0] * 24 + [20.0])
    assert count_sprints(speeds, frame_rate=25) == 1


def test_speed_band_shares_sum_to_one() -> None:
    shares = speed_band_shares(np.array([1.0, 8.0, 15.0, 20.0, 30.0, 3.0]))
    assert abs(sum(shares) - 1.0) < 1e-4
    assert shares[0] == round(2 / 6, 5)


def test_pass_bands_cover_every_length() -> None:
    assert [pass_band(x) for x in (0.0, 9.99, 10.0, 45.0, 80.0)] == ["0-10", "0-10", "10-20", "40-60", "60+"]


def test_the_reference_scores_itself_perfectly() -> None:
    reference = load_reference()
    rows = evaluate(reference, reference)
    assert len(rows) == len(CHECKS) >= 35
    assert all(row["pass"] and row["deviation"] == 0 for row in rows)


def test_a_small_scorecard_run_reports_every_check() -> None:
    report = scorecard(matches=2, seed=9, workers=2)
    assert report["total"] == len(CHECKS)
    assert 0 <= report["passed"] <= report["total"]
    assert report["summary"]["events"]["matches"] == 2
    assert markdown(report).count("\n|") == len(CHECKS) + 2
