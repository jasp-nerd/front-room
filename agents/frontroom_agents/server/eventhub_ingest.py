"""The live match feed: the room server follows a match on Azure Event Hubs, event by event, as it happens.

    uv run python -m frontroom_agents.server.publish_match --from 61:00 --speed 2  # onto the hub
    FRONTROOM_INGEST=eventhubs uv run uvicorn frontroom_agents.server.app:app --port 8787

`publish_match.py` sends each SynthLeague event, in match time, to the `match-events` hub as the same
JSON the engine writes to events.jsonl, keyed by match. With FRONTROOM_INGEST=eventhubs the server reads the
hub from "latest" (a demo starts now; nothing is replayed) and keeps every event it has received, per match.
When a goal comes in that stands, every room following the match gets the same goal flow as the studio's
Arm button.

Whether a goal stands comes from the match source, which has read the match's amendments: a goal that VAR
ruled out is never armed. Without FRONTROOM_INGEST the server keeps playing the match from its file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Protocol

from .demo_source import demo_source
from .show import MatchSource

log = logging.getLogger(__name__)


class Feed(Protocol):
    """Match events, one dict per event, in the order they arrive."""

    def events(self) -> AsyncIterator[dict]: ...


@dataclass
class EventHubFeed:
    """Reads the hub from the latest event onward, on every partition, through one consumer group."""

    connection: str
    hub: str
    consumer_group: str

    @classmethod
    def from_env(cls) -> EventHubFeed:
        return cls(
            os.environ["FRONTROOM_EVENTHUB_CONNECTION"],
            os.environ.get("FRONTROOM_EVENTHUB_NAME", "match-events"),
            os.environ.get("FRONTROOM_EVENTHUB_CONSUMER_GROUP", "$Default"),
        )

    async def events(self) -> AsyncIterator[dict]:
        from azure.eventhub.aio import EventHubConsumerClient

        arrived: asyncio.Queue[dict] = asyncio.Queue()

        async def on_event(_partition, event) -> None:
            if event is None:
                return
            try:
                arrived.put_nowait(json.loads(event.body_as_str()))
            except json.JSONDecodeError:
                log.warning("skipped a feed message that is not JSON")

        client = EventHubConsumerClient.from_connection_string(
            self.connection, consumer_group=self.consumer_group, eventhub_name=self.hub
        )
        receiving = asyncio.create_task(client.receive(on_event=on_event, starting_position="@latest"))
        try:
            while True:
                yield await arrived.get()
        finally:
            receiving.cancel()
            await client.close()


@dataclass
class Ingest:
    """Everything the feed has delivered, per match, and which of its goals have been armed."""

    source: MatchSource
    on_goal: Callable[[int], Awaitable[object]]
    """Arms the source's goal at this index in every room following the match."""
    received: dict[str, list[dict]] = field(default_factory=dict)
    armed: set[int] = field(default_factory=set)
    ignored: int = 0
    _arming: set[asyncio.Task] = field(default_factory=set, repr=False)

    async def follow(self, feed: Feed) -> None:
        async for event in feed.events():
            self.take(event)

    def take(self, event: dict) -> None:
        if event.get("matchId") != self.source.match_id:
            self.ignored += 1
            return
        events = self.received.setdefault(self.source.match_id, [])
        events.append(event)
        if event.get("type") != "goal" or event.get("amends"):
            return
        index = self._standing_goal(events, event)
        if index is None or index in self.armed:
            return
        self.armed.add(index)
        # A goal's investigation takes seconds; the feed keeps flowing meanwhile.
        task = asyncio.create_task(self.on_goal(index))
        self._arming.add(task)
        task.add_done_callback(self._arming.discard)

    def _standing_goal(self, events: list[dict], goal: dict) -> int | None:
        """The index of the source goal this feed goal scored, or None if it doesn't stand."""
        shots = [e for e in events if e.get("type") == "shot" and e.get("seq", 0) < goal.get("seq", 0)]
        if not shots:
            return None
        shot_id = max(shots, key=lambda e: e["seq"])["id"]
        return next((i for i, g in enumerate(self.source.goals) if g.shot_id == shot_id), None)

    def status(self) -> dict:
        events = self.received.get(self.source.match_id, [])
        last = events[-1] if events else None
        return {
            "following": self.source.match_id,
            "events": len(events),
            "ignored": self.ignored,
            "goalsArmed": sorted(self.armed),
            "last": {k: last[k] for k in ("id", "type", "period", "clockMs") if k in last} if last else None,
        }


def _report_if_failed(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        log.error("the live match feed stopped", exc_info=task.exception())


current: Ingest | None = None
"""The running ingest, when the server follows the feed (for /ingest)."""


@asynccontextmanager
async def following_the_feed(on_goal: Callable[[int], Awaitable[object]], feed: Feed | None = None):
    """Follows the hub for as long as the server runs, if FRONTROOM_INGEST=eventhubs (or a feed is given)."""
    global current
    if feed is None and os.environ.get("FRONTROOM_INGEST") != "eventhubs":
        yield None
        return
    current = Ingest(demo_source(), on_goal)
    task = asyncio.create_task(current.follow(feed or EventHubFeed.from_env()))
    task.add_done_callback(_report_if_failed)
    try:
        yield current
    finally:
        task.cancel()
        current = None
