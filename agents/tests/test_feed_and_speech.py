"""The live feed (Event Hubs ingest) and described audio (Azure AI Speech), with in-memory stand-ins."""

import asyncio
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from frontroom_agents.server import app as server
from frontroom_agents.server.demo_source import demo_source
from frontroom_agents.server.eventhub_ingest import Ingest, following_the_feed
from frontroom_agents.server.speech import Narrator, clip_id

MP3 = b"ID3-fake-mp3"


class ListFeed:
    """A feed that delivers a fixed list of events, as Event Hubs would deliver them one by one."""

    def __init__(self, events: list[dict]):
        self._events = events

    async def events(self) -> AsyncIterator[dict]:
        for event in self._events:
            await asyncio.sleep(0)
            yield event


def test_the_feed_arms_every_goal_that_stands_and_nothing_else():
    source = demo_source()
    armed: list[int] = []

    async def on_goal(index: int) -> None:
        armed.append(index)

    async def go():
        ingest = Ingest(source, on_goal)
        await ingest.follow(ListFeed([*source.events, {"matchId": "another-match", "type": "goal"}]))
        await asyncio.sleep(0)
        return ingest

    ingest = asyncio.run(go())
    # VAR's disallowed goal is in the feed but never armed; each standing goal is armed exactly once.
    assert sorted(armed) == list(range(len(source.goals)))
    assert ingest.ignored == 1
    assert ingest.status()["events"] == len(source.events)


def test_a_goal_arriving_on_the_feed_runs_the_room_like_the_arm_button():
    source = demo_source()
    featured = source.goals[source.featured]
    shot = next(e for e in source.events if e["id"] == featured.shot_id)
    # The feed from half a minute before the featured shot to just after its goal.
    window = [e for e in source.events if shot["seq"] - 40 <= e["seq"] <= shot["seq"] + 3]

    server.shows.clear()
    with TestClient(server.app) as client:
        client.post("/rooms/feed/demo")

        async def go():
            async with following_the_feed(server.goal_in_every_room, feed=ListFeed(window)) as ingest:
                while source.featured not in ingest.armed:
                    await asyncio.sleep(0.01)
                while not server.shows["feed"].rounds:
                    await asyncio.sleep(0.05)
                return ingest.status()

        status = asyncio.run(go())
    assert source.featured in status["goalsArmed"]
    assert server.shows["feed"].rounds[0].decision.winner == "where-it-started"


def test_described_audio_reaches_only_the_fan_who_listens(monkeypatch):
    async def fake_speech(text: str, lang: str) -> bytes:
        assert text and lang == "en"
        return MP3

    monkeypatch.setattr(server, "narrator", Narrator(fake_speech))
    server.shows.clear()
    with TestClient(server.app) as client:
        joined = client.post("/rooms/ears/demo").json()
        sam, rob = joined["sam"]["token"], joined["rob"]["token"]
        with (
            client.websocket_connect(f"/rooms/ears/ws?screen=phone&fan=sam&token={sam}") as sam_phone,
            client.websocket_connect(f"/rooms/ears/ws?screen=phone&fan=rob&token={rob}") as rob_phone,
        ):
            client.post("/rooms/ears/goals/featured")
            sam_cue = next(m for m in iter(sam_phone.receive_json, None) if m["type"] == "cue")["cue"]
            rob_cue = next(m for m in iter(rob_phone.receive_json, None) if m["type"] == "cue")["cue"]

        link = sam_cue["fields"]["audio"]
        clip = link.split("/audio/")[1].split(".mp3")[0]
        assert clip == clip_id(f"{sam_cue['fields']['headline']}. {sam_cue['fields']['line']}", "en")
        assert "audio" not in rob_cue["fields"]

        heard = client.get(link)
        assert heard.status_code == 200 and heard.content == MP3
        assert heard.headers["content-type"] == "audio/mpeg"
        # The audio is as private as the cue: a wrong token, or another fan's, gets nothing.
        assert client.get(f"/rooms/ears/audio/{clip}.mp3?fan=sam&token=wrong").status_code == 403
        assert client.get(f"/rooms/ears/audio/{clip}.mp3?fan=rob&token={rob}").status_code == 404
