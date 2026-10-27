from frontroom_agents.evals.fairness import director, loudest_wins, run


def test_the_director_never_breaks_neutral_framing_and_serves_the_worst_off_fan_better():
    ours, baseline = run(director, 400, seed=1), run(loudest_wins, 400, seed=1)
    assert ours["neutral_violations"] == 0 < baseline["neutral_violations"]
    assert ours["worst_off_fan_served"] >= baseline["worst_off_fan_served"]
