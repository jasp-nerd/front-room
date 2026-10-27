import numpy as np
import pytest

from frontroom_engine.sim import ball
from frontroom_engine.sim.shots import GOAL, ShotSituation, expected_goal, resolve_shots, uniform_columns


@pytest.mark.parametrize("distance", [8.0, 15.0, 25.0, 35.0])
def test_ground_pass_arrives_at_its_target_with_the_planned_pace(distance: float) -> None:
    arrival = 7.0
    speed = float(ball.ground_launch_speed(np.array(distance), np.array(arrival)))
    duration = float(ball.ground_flight_time(np.array(speed), np.array(arrival)))
    positions, velocities = ball.integrate(
        np.zeros(3), np.array([speed, 0.0, 0.0]), round(duration / ball.TICK)
    )
    assert positions[-1, 0, 0] == pytest.approx(distance, abs=1.0)
    assert np.linalg.norm(velocities[-1, 0]) == pytest.approx(arrival, abs=0.8)


def test_a_rolling_ball_only_slows_down() -> None:
    _, velocities = ball.integrate(np.zeros(3), np.array([15.0, 2.0, 0.0]), 150)
    speeds = np.linalg.norm(velocities[:, 0], axis=1)
    assert np.all(np.diff(speeds) <= 1e-9)
    assert speeds[-1] < 0.5


@pytest.mark.parametrize(("distance", "angle"), [(30.0, 25.0), (50.0, 35.0)])
def test_lofted_pass_first_lands_near_its_target(distance: float, angle: float) -> None:
    speed, _ = ball.lofted_launch(distance, angle)
    velocity = ball.velocity_towards(np.zeros(3), np.array([1.0, 0.0]), speed, angle)
    positions, velocities = ball.integrate(np.array([0.0, 0.0, 0.11]), velocity, 300, dt=0.02)
    first_bounce = int(np.argmax((velocities[1:, 0, 2] >= 0) & (velocities[:-1, 0, 2] < 0))) + 1
    assert positions[first_bounce, 0, 0] == pytest.approx(distance, rel=0.1)


def _situation(distance: float, pressure: float = 0.2, penalty: bool = False) -> ShotSituation:
    return ShotSituation(
        start=np.array([105.0 - distance, 34.0, 0.11]),
        goal_x=105.0,
        keeper_pos=np.array([104.0, 34.0]),
        keeper_reaction=0.24,
        keeper_skill=0.75,
        blockers=np.zeros((0, 2)),
        finishing=1.2,
        pressure=pressure,
        header=False,
        penalty=penalty,
    )


def test_physical_xg_falls_with_distance_and_pressure() -> None:
    rng = np.random.default_rng(0)
    close, mid, far = (expected_goal(_situation(d), rng)[0] for d in (8.0, 16.0, 28.0))
    assert close > mid > far
    assert far < 0.08
    assert (
        expected_goal(_situation(12.0, pressure=0.9), rng)[0]
        < expected_goal(_situation(12.0, pressure=0.0), rng)[0]
    )


def test_a_defender_on_the_line_of_the_shot_blocks_some_attempts() -> None:
    rng = np.random.default_rng(1)
    open_shot = _situation(18.0)
    blocked = ShotSituation(**{**vars(open_shot), "blockers": np.array([[95.0, 34.0]])})
    n = 2000
    normals, uniforms = rng.standard_normal((n, 3)), rng.random((n, uniform_columns(1)))
    with_blocker = resolve_shots(blocked, normals, uniforms)
    without = resolve_shots(open_shot, normals, uniforms[:, : uniform_columns(0)])
    assert np.mean(with_blocker.outcome == GOAL) < np.mean(without.outcome == GOAL)
