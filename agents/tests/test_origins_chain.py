from frontroom_agents.origins.chain import DECISIVE_FLOOR, credit, scoring_possession, verdict
from frontroom_agents.origins.xt import ExpectedThreat


def event(seq, side, type_, start, end=None, result="success", **detail):
    e = {
        "id": f"ev-{seq}",
        "seq": seq,
        "period": 2,
        "side": side,
        "playerId": f"{side}-{seq}",
        "type": type_,
        "result": result,
        "start": {"x": start[0], "y": start[1]},
    }
    if end:
        e["end"] = {"x": end[0], "y": end[1]}
    if detail:
        e["detail"] = detail
    return e


# Ashvale lose it on halfway, Kestrel (attacking right) win it back and work it into the box.
MATCH = [
    event(1, "away", "pass", (50, 30), (56, 29)),
    event(2, "home", "tackle", (56, 29)),
    event(3, "home", "pass", (57, 30), (63, 21)),
    event(4, "home", "pass", (63, 21), (77, 27)),
    event(5, "home", "pass", (77, 27), (90, 36)),
    event(6, "home", "shot", (90, 36), xg=0.24),
]


def test_the_scoring_possession_starts_with_the_regain():
    chain = scoring_possession(MATCH, "ev-6")
    assert [e["id"] for e in chain] == ["ev-2", "ev-3", "ev-4", "ev-5", "ev-6"]


def test_a_pass_into_the_box_adds_more_than_a_pass_sideways_on_halfway():
    credits = {c.event_id: c for c in credit(scoring_possession(MATCH, "ev-6"), ExpectedThreat(), True)}
    assert credits["ev-5"].value > credits["ev-3"].value
    assert all(c.low <= c.value <= c.high for c in credits.values())


def test_direction_of_play_is_respected():
    mirrored = [
        {**e, "start": {"x": 105 - e["start"]["x"], "y": 68 - e["start"]["y"]}}
        | ({"end": {"x": 105 - e["end"]["x"], "y": 68 - e["end"]["y"]}} if "end" in e else {})
        for e in MATCH
    ]
    model = ExpectedThreat()
    right = credit(scoring_possession(MATCH, "ev-6"), model, True)
    left = credit(scoring_possession(mirrored, "ev-6"), model, False)
    assert [c.value for c in right] == [c.value for c in left]


def test_credit_is_shared_when_no_action_clearly_stands_out():
    result = verdict(credit(scoring_possession(MATCH, "ev-6"), ExpectedThreat(), True))
    assert result.kind == "shared"
    assert result.top.value < DECISIVE_FLOOR or result.top.low <= result.runner_up.high


def test_one_pass_that_splits_the_defence_is_decisive():
    through_ball = [
        *MATCH[:3],
        event(4, "home", "pass", (63, 34), (99, 34)),
        event(5, "home", "shot", (99, 34), xg=0.6),
    ]
    result = verdict(credit(scoring_possession(through_ball, "ev-5"), ExpectedThreat(), True))
    assert result.kind == "decisive"
    assert result.top.event_id == "ev-4"


def test_a_goal_from_a_rebound_is_shared_and_credits_the_shot():
    scramble = [event(1, "away", "clearance", (95, 34)), event(2, "home", "shot", (96, 33), xg=0.4)]
    result = verdict(credit(scoring_possession(scramble, "ev-2"), ExpectedThreat(), True))
    assert result.kind == "shared" and result.top.event_id == "ev-2"
