import asyncio

import httpx
from fastapi.testclient import TestClient
from tests.test_session import OFFERS, PROFILES

from frontroom_agents.a2a.director_agent import CARD_PATH, agent_card
from frontroom_agents.a2a.remote import RemoteDirector, director_from_env
from frontroom_agents.mcp import studio
from frontroom_agents.personal.agent import PersonalAgent, RuleScorer
from frontroom_agents.room.demo import CANDIDATES, demo_bids, front_room
from frontroom_agents.room.director import decide
from frontroom_agents.room.session import FallbackDirector, run_round
from frontroom_agents.room.wire import decision_to_wire
from frontroom_agents.server.app import app, shows
from frontroom_agents.server.demo_source import demo_source


def comparable(decision) -> dict:
    """A decision's ledger without its timing, which differs run to run."""
    wire = decision_to_wire(decision, "room", "d")
    wire.pop("decidedInMs")
    return wire


def in_process() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def test_the_director_publishes_an_agent_card_with_its_skill():
    with TestClient(app) as client:
        card = client.get(CARD_PATH).json()
    assert card["name"] == "Front Room Director"
    assert [s["id"] for s in card["skills"]] == ["decide-shared-screen"]
    assert card["supportedInterfaces"][0]["url"].endswith("/a2a/director/")


def test_the_remote_director_decides_exactly_as_the_local_one():
    async def go():
        async with in_process() as http:
            remote = RemoteDirector(agent_card("http://test"), http=http)
            return await remote.decide(CANDIDATES, demo_bids(), front_room())

    assert comparable(asyncio.run(go())) == comparable(decide(CANDIDATES, demo_bids(), front_room()))


def test_the_room_asks_the_a2a_director_and_falls_back_to_the_same_rules():
    async def go():
        async with in_process() as http:
            reachable = FallbackDirector(RemoteDirector(agent_card("http://test"), http=http))
            over_a2a = await reachable.decide(CANDIDATES, demo_bids(), front_room())
        unreachable = FallbackDirector(RemoteDirector("http://127.0.0.1:9"), timeout_s=1.0)
        fell_back = await unreachable.decide(CANDIDATES, demo_bids(), front_room())
        return reachable, over_a2a, unreachable, fell_back

    reachable, over_a2a, unreachable, fell_back = asyncio.run(go())
    expected = comparable(decide(CANDIDATES, demo_bids(), front_room()))
    assert reachable.used == "a2a" and comparable(over_a2a) == expected
    assert unreachable.used == "local-fallback" and comparable(fell_back) == expected


def test_the_director_is_reached_over_a2a_only_when_configured(monkeypatch):
    monkeypatch.delenv("FRONTROOM_DIRECTOR_URL", raising=False)
    assert director_from_env("4821") is None
    monkeypatch.setenv("FRONTROOM_DIRECTOR_URL", "http://test")
    assert isinstance(director_from_env("4821"), FallbackDirector)


def test_a_room_round_can_ask_a_director_found_by_url():
    agents = [PersonalAgent(fan, profile, RuleScorer()) for fan, profile in PROFILES.items()]

    async def go():
        async with in_process() as http:
            remote = RemoteDirector("http://test", http=http)
            over_a2a = await run_round(agents, OFFERS, front_room(), director=remote)
        local = await run_round(agents, OFFERS, front_room())
        return over_a2a, local

    over_a2a, local = asyncio.run(go())
    assert comparable(over_a2a.decision) == comparable(local.decision)


def test_studio_tools_investigate_a_goal_and_read_the_fairness_report():
    # The demo story's goal, read from the shipped match rather than written in, so regenerating it is safe.
    source = demo_source()
    featured = source.goals[source.featured]

    async def go():
        goal = await studio.studio.call_tool(
            "investigate_goal", {"match_id": source.match_id, "shot_id": featured.shot_id}
        )
        report = await studio.studio.call_tool("fairness_report", {})
        return goal.structured_content, report.structured_content

    goal, report = asyncio.run(go())
    assert goal["insight"]["kind"] == "where_it_started"
    assert goal["copy"]["en_headline"]
    assert [step["role"] for step in goal["trace"]][-1] == "check"
    assert report["director"]["neutral_violations"] == 0


def test_the_room_ledger_tool_reads_a_live_room():
    shows.clear()
    with TestClient(app) as client:
        client.post("/rooms/m1/demo")
        client.post("/rooms/m1/goals/0")
        ledger = asyncio.run(studio.studio.call_tool("room_ledger", {"room": "m1"})).structured_content
        empty = asyncio.run(studio.studio.call_tool("room_ledger", {"room": "nobody"})).structured_content
    assert ledger["decision"]["roomId"] == "m1"
    assert any(c["won"] for c in ledger["decision"]["candidates"])
    assert empty["decision"] is None


def test_studio_tools_are_listed_over_streamable_http():
    headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
    with TestClient(app) as client:
        response = client.post(
            "/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert names == {"investigate_goal", "room_ledger", "fairness_report"}
