"""The demo storyline is present in the files a client would read, not just in memory."""

import json

import pytest

from frontroom_engine.io import MatchFiles, read_events


@pytest.fixture(scope="module")
def story(demo: MatchFiles) -> dict[str, dict]:
    return {beat["beat"]: beat for beat in json.loads(demo.truth.read_text())["story"]}


@pytest.fixture(scope="module")
def events(demo: MatchFiles) -> dict[str, dict]:
    return {event["id"]: event for event in read_events(demo.events) if "amends" not in event}


def _minute(event: dict) -> float:
    return (event["period"] - 1) * 45 + event["clockMs"] / 60000


def test_the_demo_is_kestrel_at_home_to_ashvale(demo: MatchFiles) -> None:
    metadata = json.loads(demo.metadata.read_text())
    assert (metadata["home"]["name"], metadata["away"]["name"]) == ("Kestrel FC", "Ashvale Athletic")
    assert metadata["steered"]


def test_ashvale_goal_is_ruled_out_by_var_for_offside_just_before_the_hour(
    story: dict[str, dict], events: dict[str, dict], demo: MatchFiles
) -> None:
    beat = story["var_disallowed_goal"]
    goal, decision = events[beat["events"]["goalEvent"]], events[beat["events"]["varDecisionEvent"]]
    assert goal["side"] == "away" and goal["type"] == "goal"
    assert 57.0 <= _minute(goal) <= 60.0
    assert decision["type"] == "var_decision" and decision["detail"]["reason"] == "offside"
    amendment = next(e for e in read_events(demo.events) if e.get("amends") == goal["id"])
    assert amendment["detail"]["disallowed"] is True


def test_okafor_scores_after_mensah_presses_lund_into_losing_the_ball_near_halfway(
    story: dict[str, dict], events: dict[str, dict]
) -> None:
    win, goal_beat = story["press_win"], story["okafor_goal"]
    press, won = events[win["events"]["pressEvent"]], events[win["events"]["winEvent"]]
    goal = events[goal_beat["events"]["goalEvent"]]
    assert press["type"] == "press" and press["playerId"] == "kes-06-mensah"
    assert press["detail"]["onPlayer"] == "ash-04-lund"
    assert abs(press["end"]["x"] - 52.5) <= 17.0
    assert won["side"] == "home" and won["type"] in ("tackle", "interception")
    assert goal["playerId"] == "kes-09-okafor" and goal["result"] == "success"
    assert 60.5 <= _minute(goal) <= 64.0
    assert 10.0 <= goal_beat["detail"]["secondsFromWin"] <= 28.0
    passes = [events[i] for i in goal_beat["events"]["passEvents"]]
    assert 3 <= len(passes) <= 6
    assert all(p["side"] == "home" and p["result"] == "success" for p in passes)


def test_steering_cost_is_reported(demo: MatchFiles) -> None:
    steering = json.loads(demo.truth.read_text())["steering"]
    assert steering["branches"]
    assert steering["conditioningNats"] > 0
