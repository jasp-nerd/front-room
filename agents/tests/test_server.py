import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from frontroom_agents.server.app import app, shows

JOINS = {
    "rob": "Kestrel fan. Show me the shape, I want numbers.",
    "ana": "Soy de Ashvale. Solo lo importante, en español por favor.",
    "leo": "I'm 10 and I like goals",
    "sam": "Kestrel. Big text, talk me through it.",
}


def test_a_goal_reaches_every_screen_and_phones_stay_private():
    shows.clear()
    with TestClient(app) as client:
        joined = {
            fan: client.post("/rooms/r1/fans", json={"fan": fan, "told": told}).json()
            for fan, told in JOINS.items()
        }
        understood = {fan: j["understood"] for fan, j in joined.items()}
        tokens = {fan: j["token"] for fan, j in joined.items()}
        assert understood["ana"]["club"] == "ashvale" and understood["ana"]["language"] == "es"
        assert understood["leo"]["depth"] == "kid"

        with (
            client.websocket_connect("/rooms/r1/ws?screen=tv") as tv,
            client.websocket_connect("/rooms/r1/ws?screen=room") as room,
            client.websocket_connect(f"/rooms/r1/ws?screen=phone&fan=ana&token={tokens['ana']}") as ana,
            client.websocket_connect(f"/rooms/r1/ws?screen=phone&fan=rob&token={tokens['rob']}") as rob,
        ):
            result = client.post("/rooms/r1/goals/0").json()
            assert result["winner"] == "where-it-started"

            tv_cue = json.loads(tv.receive_text())["cue"]
            assert tv_cue["destination"] == "room-tv" and tv_cue["fields"]["neutral"] is True

            kinds: list[str] = []
            while not kinds or kinds[-1] != "decision":
                kinds.append(json.loads(room.receive_text())["type"])
            assert kinds[0] == "investigating" and kinds[-2:] == ["insight", "decision"]
            assert kinds.count("step") == 14  # seven steps, each reported starting and finishing

            ana_cue = json.loads(ana.receive_text())["cue"]
            assert ana_cue["lang"] == "es" and ana_cue["agentId"] == "ana"
            rob_cue = json.loads(rob.receive_text())["cue"]
            assert rob_cue["agentId"] == "rob"
            assert rob_cue["fields"]["onTv"] is False  # his pressing map lost the TV, so it came to his phone


def test_a_phone_socket_needs_its_fans_token():
    shows.clear()
    with TestClient(app) as client:
        token = client.post("/rooms/r2/fans", json={"fan": "rob", "told": "Kestrel"}).json()["token"]
        for query in ("fan=rob", "fan=rob&token=wrong", f"fan=ana&token={token}"):
            with (
                pytest.raises(WebSocketDisconnect),
                client.websocket_connect(f"/rooms/r2/ws?screen=phone&{query}") as s,
            ):
                s.receive_text()


def test_a_second_goal_while_the_first_overlay_is_on_air_is_held():
    shows.clear()
    with TestClient(app) as client:
        client.post("/rooms/r3/demo")
        assert client.post("/rooms/r3/goals/0").json()["winner"] == "where-it-started"
        assert client.post("/rooms/r3/goals/0").json()["winner"] is None


def test_oversized_or_badly_named_input_is_refused():
    shows.clear()
    with TestClient(app) as client:
        assert client.post("/rooms/r4/fans", json={"fan": "rob", "told": "x" * 401}).status_code == 422
        assert client.post("/rooms/Bad Room/fans", json={"fan": "rob", "told": "hi"}).status_code in (
            400,
            404,
        )
        assert client.post("/rooms/r4/goals/99").status_code == 404


def test_the_demo_can_leave_ana_out_and_then_nothing_is_held_for_fairness():
    with TestClient(app) as client:
        joined = client.post("/rooms/tea/demo?without=ana").json()
        client.post("/rooms/tea/goals/featured")
    assert sorted(joined) == ["leo", "rob", "sam"]
    show = shows["tea"]
    assert show.clubs_present == {"kestrel"}
    assert not any(c.struck_by == "neutral-framing" for c in show.rounds[0].decision.candidates)
