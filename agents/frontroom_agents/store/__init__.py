"""What the room server keeps, so a room survives a restart and the broadcaster can audit every decision.

    store = Store(memory_containers())          # tests, and running without Cosmos
    async with open_store() as store: ...       # Azure Cosmos DB when FRONTROOM_COSMOS_* is set

What is kept, and what is not:
- **Rooms:** who joined (fan ids only), whether both clubs are in the room, how long each fan has waited
  for the TV, and when the TV's last overlay ends. A fan's own words and profile (club, language, how they
  watch) are not kept: they belong to that fan's helper, and the Director only ever sees its bids. After a
  restart, a room keeps its fairness clock and its ledger, and phones rejoin with their own words.
- **Ledger:** every decision, with the bids, the fairness weights, the house rules that struck a pick, the
  winner and who was dropped for being late. The room view and the studio already show all of it.
- **As-run:** every cue sent to a screen, and when.
- **Checkpoints:** the investigation in flight, after each superstep, so a restart resumes it.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from ..telemetry import span
from .checkpoints import DocumentCheckpointStorage
from .documents import Container, cosmos_configured, cosmos_containers, memory_containers

__all__ = ["DocumentCheckpointStorage", "Store", "memory_containers", "open_store"]


class Store:
    def __init__(self, containers: dict[str, Container], kind: str = "memory"):
        self.containers = containers
        self.kind = kind  # "cosmos" or "memory", for /health

    async def _write(self, container: str, document: dict[str, Any]) -> None:
        with span("store.write", container=container, backend=self.kind):
            await self.containers[container].upsert(document)

    async def save_room(
        self,
        room: str,
        fans: list[str],
        both_clubs: bool,
        waited: dict[str, float],
        overlay_ends_at: int | None,
    ) -> None:
        """The room as the Director may know it. `waited` is seconds each fan has gone without the TV."""
        await self._write(
            "rooms",
            {
                "id": room,
                "room": room,
                "fans": fans,
                "bothClubs": both_clubs,
                "waited": waited,
                "overlayEndsAt": overlay_ends_at,
                "savedAt": time.time(),
            },
        )

    async def rooms(self) -> list[dict[str, Any]]:
        return await self.containers["rooms"].query()

    async def record_decision(
        self, room: str, decision: dict[str, Any], bids: list[dict[str, Any]], dropped: list[str]
    ) -> None:
        await self._write(
            "ledger",
            {
                "id": f"{decision['decisionId']}-{uuid.uuid4().hex[:8]}",
                "room": room,
                "at": time.time(),
                "decision": decision,
                "bids": bids,
                "dropped": dropped,
            },
        )

    async def ledger(self, room: str) -> list[dict[str, Any]]:
        return sorted(await self.containers["ledger"].query(room), key=lambda d: d["at"])

    async def record_cue(self, room: str, screen: str, cue: dict[str, Any]) -> None:
        await self._write(
            "asrun",
            {
                "id": uuid.uuid4().hex,
                "room": room,
                "screen": screen,
                "at": time.time(),
                "cueId": cue["cueId"],
                "template": cue["template"],
                "pts": cue["pts"],
                "lang": cue["lang"],
                "overlay": cue["fields"].get("overlay", cue.get("template")),
            },
        )

    async def as_run(self, room: str) -> list[dict[str, Any]]:
        return sorted(await self.containers["asrun"].query(room), key=lambda d: d["at"])

    def checkpoints(self, run_key: str) -> DocumentCheckpointStorage:
        return DocumentCheckpointStorage(self.containers["checkpoints"], run_key)

    async def unfinished(self) -> list[str]:
        """The run keys ("room/shot") of investigations that left checkpoints: they never finished."""
        return sorted({d["workflow"] for d in await self.containers["checkpoints"].query()})


@asynccontextmanager
async def open_store() -> AsyncIterator[Store]:
    """Azure Cosmos DB when it is configured, otherwise memory (the room then forgets on restart)."""
    if cosmos_configured():
        async with cosmos_containers() as containers:
            yield Store(containers, "cosmos")
    else:
        yield Store(memory_containers())
