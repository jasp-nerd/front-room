"""The investigation survives the room server dying part-way: it resumes from its last checkpoint."""

import asyncio

import pytest

from frontroom_agents.origins.workflow import Request, investigate
from frontroom_agents.server.demo_source import demo_source
from frontroom_agents.store import Store, memory_containers


class ServerDied(Exception):
    """Stands in for the process stopping: the run is abandoned mid-workflow."""


def featured_request() -> Request:
    source = demo_source()
    goal = source.goals[source.featured]
    return Request(
        source.match_id, goal.shot_id, goal.pts, source.events, source.players, goal.attacking_right
    )


def test_an_interrupted_investigation_resumes_where_it_stopped_with_the_same_answer():
    request = featured_request()
    store = Store(memory_containers())
    run_key = f"4821/{request.shot_id}"

    async def go():
        uninterrupted = await investigate(request)

        async def die_at_verify(role, done):
            if role == "verify" and done is None:
                raise ServerDied

        with pytest.raises(ServerDied):
            await investigate(request, on_step=die_at_verify, checkpoints=store.checkpoints(run_key))
        assert await store.unfinished() == [run_key]

        # A new storage object on the same documents: what a restarted server would open.
        started: list[str] = []

        async def watch(role, done):
            if done is None:
                started.append(role)

        resumed = await investigate(request, on_step=watch, checkpoints=store.checkpoints(run_key))
        return uninterrupted, resumed, started, await store.unfinished()

    uninterrupted, resumed, started, left = asyncio.run(go())

    assert started == ["verify", "writer", "check"], "steps that finished before the stop are not rerun"
    assert resumed.copy == uninterrupted.copy
    assert resumed.verdict == uninterrupted.verdict
    assert resumed.story == uninterrupted.story
    assert [s.role for s in resumed.trace][-2:] == ["resume", "check"]
    assert left == [], "a finished investigation leaves no checkpoints behind"


def test_checkpoints_round_trip_through_the_document_encoding():
    request = featured_request()
    store = Store(memory_containers())

    async def go():
        storage = store.checkpoints("room/shot")
        await investigate(request, checkpoints=storage)

    # The storage clears itself after a finished run; a fresh run must leave nothing behind either.
    asyncio.run(go())
    assert asyncio.run(store.unfinished()) == []
