from frontroom_agents.room.demo import (
    GOAL_PTS,
    KEEPERS_VIEW,
    PRESSING_MAP,
    WHERE_IT_STARTED,
    demo_bids,
    front_room,
)
from frontroom_agents.room.director import (
    MIN_GAP_MS,
    Bid,
    Candidate,
    Constraint,
    decide,
    fairness_weight,
)


def test_highest_raw_bid_loses_to_neutral_framing_when_both_clubs_are_in_the_room():
    decision = decide([WHERE_IT_STARTED, PRESSING_MAP, KEEPERS_VIEW], demo_bids(), front_room())

    scores = {c.candidate_id: c for c in decision.candidates}
    assert scores[PRESSING_MAP.id].raw_score > scores[WHERE_IT_STARTED.id].raw_score
    assert scores[PRESSING_MAP.id].struck_by is Constraint.NEUTRAL_FRAMING
    assert decision.winner == WHERE_IT_STARTED.id


def test_one_club_room_lets_partisan_overlays_compete():
    decision = decide([WHERE_IT_STARTED, PRESSING_MAP], demo_bids(), front_room(both_clubs_present=False))
    assert decision.winner == PRESSING_MAP.id


def test_every_fan_whose_favourite_lost_gets_it_on_their_phone():
    decision = decide([WHERE_IT_STARTED, PRESSING_MAP, KEEPERS_VIEW], demo_bids(), front_room())
    assert decision.delivered_privately == {
        "rob": PRESSING_MAP.id,
        "ana": KEEPERS_VIEW.id,
        "sam": PRESSING_MAP.id,
    }


def test_waiting_longer_counts_for_more_up_to_a_cap():
    assert fairness_weight(0) == 1.0
    assert round(fairness_weight(540), 3) == 1.375
    assert fairness_weight(10_000) == fairness_weight(720)


def test_fairness_weight_can_change_the_winner():
    a = Candidate("a", GOAL_PTS, partisan=False)
    b = Candidate("b", GOAL_PTS, partisan=False)
    bids = [Bid("rob", "a", 0.8), Bid("leo", "b", 0.7)]
    patient_leo = front_room(seconds_without_screen={"rob": 0, "leo": 720})
    assert decide([a, b], bids, patient_leo).winner == "b"
    assert decide([a, b], bids, front_room(seconds_without_screen={})).winner == "a"


def test_nothing_from_the_future_reaches_the_tv():
    future = Candidate("future-goal", GOAL_PTS + 60_000, partisan=False)
    decision = decide([future], [Bid("leo", future.id, 1.0)], front_room())
    assert decision.winner is None
    assert decision.candidates[0].struck_by is Constraint.SPOILER_GATE


def test_var_check_and_cooldown_hold_the_screen():
    bids = demo_bids()
    assert decide([WHERE_IT_STARTED], bids, front_room(var_check=True)).winner is None
    recently = front_room(last_overlay_end_pts=GOAL_PTS + 4_000 - MIN_GAP_MS // 2)
    assert decide([WHERE_IT_STARTED], bids, recently).candidates[0].struck_by is Constraint.MIN_GAP


def test_same_inputs_give_the_same_decision():
    first = decide([WHERE_IT_STARTED, PRESSING_MAP, KEEPERS_VIEW], demo_bids(), front_room())
    second = decide([WHERE_IT_STARTED, PRESSING_MAP, KEEPERS_VIEW], demo_bids(), front_room())
    assert first.winner == second.winner
    assert first.candidates == second.candidates


def test_an_agent_that_wants_everything_cannot_outvote_the_room():
    greedy = [Bid("rob", c.id, 1.0) for c in (WHERE_IT_STARTED, PRESSING_MAP, KEEPERS_VIEW)]
    modest = [Bid("ana", KEEPERS_VIEW.id, 0.0), Bid("leo", WHERE_IT_STARTED.id, 0.6)]
    one_club = front_room(both_clubs_present=False, seconds_without_screen={})
    decision = decide([WHERE_IT_STARTED, PRESSING_MAP, KEEPERS_VIEW], greedy + modest, one_club)
    scores = {c.candidate_id: c.raw_score for c in decision.candidates}
    assert round(scores[PRESSING_MAP.id], 4) == round(1 / 3, 4)
    assert decision.winner == WHERE_IT_STARTED.id


def test_negative_or_outsider_bids_cannot_buy_the_tv():
    a = Candidate("a", GOAL_PTS, partisan=False)
    b = Candidate("b", GOAL_PTS, partisan=False)
    bids = [
        Bid("rob", "a", 5.0),
        Bid("rob", "b", -4.0),
        Bid("leo", "b", 1.0),
        Bid("ana", "b", 1.0),
        Bid("stranger", "a", 1.0),
    ]
    decision = decide([a, b], bids, front_room(seconds_without_screen={"rob": -9999}))
    assert decision.winner == "b"
    assert all(c.raw_score >= 0 for c in decision.candidates)
