"""Play a SynthLeague match onto Azure Event Hubs, event by event, in match time: the live synthetic feed.

    set -a; source .env; set +a
    uv run python -m frontroom_agents.server.publish_match --from 61:00 --speed 2  # goal in ~20 s
    uv run python -m frontroom_agents.server.publish_match --speed 30 --seconds 30  # half a minute, 30x fast
    uv run python -m frontroom_agents.server.publish_match --dry-run --from 61:00 --seconds 10

Each event goes out as the engine's own JSON (one events.jsonl line), with the match id as the partition key,
so a match's events stay in order. The gaps between sends are the gaps in match time, divided by --speed;
half-time is skipped. The room server follows the hub with FRONTROOM_INGEST=eventhubs
(eventhub_ingest.py, next to this file).

Reads FRONTROOM_EVENTHUB_CONNECTION and FRONTROOM_EVENTHUB_NAME.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

DEFAULT_MATCH = Path(__file__).resolve().parent / "demo_match"


def match_ms(clock: str) -> int:
    """A scorebug clock ("61:00") as milliseconds of match time from kick-off."""
    minutes, seconds = clock.split(":")
    return (int(minutes) * 60 + int(seconds)) * 1000


def event_ms(event: dict) -> int:
    """An event's match time, the way the scorebug counts it: the second half starts at 45:00."""
    return event["clockMs"] + (45 * 60_000 if event["period"] == 2 else 0)


def load(match: Path, start: int, seconds: float | None, speed: float) -> list[dict]:
    events = [json.loads(line) for line in (match / "events.jsonl").read_text().splitlines() if line]
    events = sorted((e for e in events if event_ms(e) >= start), key=lambda e: e["seq"])
    if seconds is not None:
        # --seconds is wall-clock time, so at 30x speed it covers 30x as much of the match.
        end = start + seconds * 1000 * speed
        events = [e for e in events if event_ms(e) <= end]
    return events


async def publish(events: list[dict], speed: float, dry_run: bool) -> None:
    producer = None
    if not dry_run:
        from azure.eventhub import EventData
        from azure.eventhub.aio import EventHubProducerClient

        producer = EventHubProducerClient.from_connection_string(
            os.environ["FRONTROOM_EVENTHUB_CONNECTION"],
            eventhub_name=os.environ.get("FRONTROOM_EVENTHUB_NAME", "match-events"),
        )
    try:
        previous = None
        for event in events:
            at = event_ms(event)
            if previous is not None and at > previous:
                await asyncio.sleep((at - previous) / 1000 / speed)
            previous = at
            if producer:
                batch = await producer.create_batch(partition_key=event["matchId"])
                batch.add(EventData(json.dumps(event, separators=(",", ":"))))
                await producer.send_batch(batch)
            clock = f"{at // 60_000}:{at // 1000 % 60:02d}"
            if event["type"] in ("goal", "shot") or dry_run:
                print(f"{clock}  {event['type']:<12} {event.get('playerId', '')}", flush=True)
    finally:
        if producer:
            await producer.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--match", type=Path, default=DEFAULT_MATCH, help="a folder with events.jsonl")
    parser.add_argument("--from", dest="start", default="0:00", help="match clock to start at, e.g. 61:00")
    parser.add_argument("--speed", type=float, default=1.0, help="how many times faster than real time")
    parser.add_argument("--seconds", type=float, help="stop after this many seconds of sending")
    parser.add_argument("--dry-run", action="store_true", help="print the events instead of sending them")
    args = parser.parse_args()
    events = load(args.match, match_ms(args.start), args.seconds, args.speed)
    print(f"{len(events)} events from {args.start} at {args.speed}x", flush=True)
    asyncio.run(publish(events, args.speed, args.dry_run))


if __name__ == "__main__":
    main()
