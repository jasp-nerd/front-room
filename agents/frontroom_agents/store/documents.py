"""The four document containers Front Room keeps, in Azure Cosmos DB or in memory.

Both kinds offer the same four async calls the store uses (upsert, read, query by partition, delete), so the
room server and the tests run the same code; only where the documents live differs.

    rooms        /room      one document per room: who is in it and how long each fan has waited
    ledger       /room      every decision the Director made: the fairness ledger
    asrun        /room      every cue sent to a screen, with when: the broadcaster's as-run log
    checkpoints  /workflow  Agent Framework checkpoints of investigations still in flight
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any, Protocol

CONTAINERS = ("rooms", "ledger", "asrun", "checkpoints")


class Container(Protocol):
    async def upsert(self, document: dict[str, Any]) -> None: ...
    async def read(self, item_id: str, partition: str) -> dict[str, Any] | None: ...
    async def query(self, partition: str | None = None) -> list[dict[str, Any]]: ...
    async def delete(self, item_id: str, partition: str) -> None: ...


class MemoryContainer:
    """Documents in a dict, keyed by (partition, id), for tests and for running without Cosmos."""

    def __init__(self, partition_key: str):
        self.partition_key = partition_key
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    async def upsert(self, document: dict[str, Any]) -> None:
        self.items[(document[self.partition_key], document["id"])] = dict(document)

    async def read(self, item_id: str, partition: str) -> dict[str, Any] | None:
        found = self.items.get((partition, item_id))
        return dict(found) if found else None

    async def query(self, partition: str | None = None) -> list[dict[str, Any]]:
        return [dict(d) for (p, _), d in self.items.items() if partition is None or p == partition]

    async def delete(self, item_id: str, partition: str) -> None:
        self.items.pop((partition, item_id), None)


class CosmosContainer:
    """One Azure Cosmos DB container (azure-cosmos async client), behind the same four calls."""

    def __init__(self, proxy: Any, partition_key: str):
        self.proxy = proxy
        self.partition_key = partition_key

    async def upsert(self, document: dict[str, Any]) -> None:
        await self.proxy.upsert_item(document)

    async def read(self, item_id: str, partition: str) -> dict[str, Any] | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            return _plain(await self.proxy.read_item(item_id, partition_key=partition))
        except CosmosResourceNotFoundError:
            return None

    async def query(self, partition: str | None = None) -> list[dict[str, Any]]:
        if partition is None:
            pages = self.proxy.query_items("SELECT * FROM c")
        else:
            pages = self.proxy.query_items(
                f"SELECT * FROM c WHERE c.{self.partition_key} = @p",
                parameters=[{"name": "@p", "value": partition}],
                partition_key=partition,
            )
        return [_plain(item) async for item in pages]

    async def delete(self, item_id: str, partition: str) -> None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        with suppress(CosmosResourceNotFoundError):
            await self.proxy.delete_item(item_id, partition_key=partition)


def _plain(item: dict[str, Any]) -> dict[str, Any]:
    """A document without Cosmos's own system fields (_rid, _etag, _ts, ...)."""
    return {k: v for k, v in item.items() if not k.startswith("_")}


PARTITIONS = {"rooms": "room", "ledger": "room", "asrun": "room", "checkpoints": "workflow"}


def memory_containers() -> dict[str, Container]:
    return {name: MemoryContainer(PARTITIONS[name]) for name in CONTAINERS}


def cosmos_configured() -> bool:
    return bool(os.environ.get("FRONTROOM_COSMOS_ENDPOINT") and os.environ.get("FRONTROOM_COSMOS_KEY"))


@asynccontextmanager
async def cosmos_containers() -> AsyncIterator[dict[str, Container]]:
    """The containers in the FRONTROOM_COSMOS_DATABASE database (created by infra), key auth from the
    environment. The client is closed when the room server stops."""
    from azure.cosmos.aio import CosmosClient

    async with CosmosClient(
        os.environ["FRONTROOM_COSMOS_ENDPOINT"], credential=os.environ["FRONTROOM_COSMOS_KEY"]
    ) as client:
        database = client.get_database_client(os.environ.get("FRONTROOM_COSMOS_DATABASE", "frontroom"))
        yield {
            name: CosmosContainer(database.get_container_client(name), PARTITIONS[name])
            for name in CONTAINERS
        }
