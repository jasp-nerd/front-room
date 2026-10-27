import numpy as np

from frontroom_engine.sim.noise import NoiseTape


def test_a_value_depends_only_on_its_key_not_on_call_order() -> None:
    forward, backward = NoiseTape(5), NoiseTape(5)
    keys = [("pass", tick, slot) for tick in (3, 250, 9_000) for slot in (0, 7, 21)]
    drawn_forward = [forward.normal(*key) for key in keys]
    drawn_backward = [backward.normal(*key) for key in reversed(keys)][::-1]
    for a, b in zip(drawn_forward, drawn_backward, strict=True):
        np.testing.assert_array_equal(a, b)


def test_purposes_and_slots_get_independent_values() -> None:
    tape = NoiseTape(5)
    assert not np.array_equal(tape.uniform("tackle", 10, 3), tape.uniform("tackle", 10, 4))
    assert not np.array_equal(tape.uniform("tackle", 10, 3)[:2], tape.uniform("lapse", 10, 3))


def test_a_branch_keeps_the_past_and_changes_the_future() -> None:
    tape = NoiseTape(5)
    branch = tape.branched(1_000, salt=42)
    np.testing.assert_array_equal(tape.normal_all("steer", 999), branch.normal_all("steer", 999))
    assert not np.array_equal(tape.normal_all("steer", 1_000), branch.normal_all("steer", 1_000))


def test_gumbel_noise_is_finite() -> None:
    assert np.all(np.isfinite(NoiseTape(1).gumbel("decide", 77, 2, 16)))
