"""Agent Framework checkpoint storage on a document container (Azure Cosmos DB, or memory in tests).

The workflow saves a checkpoint after every superstep. Each investigation gets its own partition (its run
key, "room/shot"), so a room server that dies mid-investigation can find the last checkpoint of exactly
that investigation and resume from it instead of starting over.

A checkpoint is encoded with Agent Framework's own encoding (safe types plus the classes the investigation
registers with `register_checkpoint_type`), then compressed: a Case carries the match's event feed, and a
Cosmos document holds at most 2 MB.
"""

from __future__ import annotations

import base64
import json
import zlib
from typing import Any

from agent_framework import WorkflowCheckpoint
from agent_framework._workflows._checkpoint_encoding import decode_checkpoint_value, encode_checkpoint_value
from agent_framework.exceptions import WorkflowCheckpointException

from .documents import Container


def _pack(checkpoint: WorkflowCheckpoint) -> str:
    encoded = encode_checkpoint_value(checkpoint.to_dict())
    return base64.b64encode(zlib.compress(json.dumps(encoded).encode(), 6)).decode()


def _unpack(data: str) -> WorkflowCheckpoint:
    encoded = json.loads(zlib.decompress(base64.b64decode(data)))
    # An empty allow-list still admits the framework's safe types and every registered class, nothing else.
    return WorkflowCheckpoint.from_dict(decode_checkpoint_value(encoded, allowed_types=frozenset()))


class DocumentCheckpointStorage:
    """Implements Agent Framework's CheckpointStorage protocol for one investigation (one run key)."""

    def __init__(self, container: Container, run_key: str):
        self.container = container
        self.run_key = run_key

    async def save(self, checkpoint: WorkflowCheckpoint) -> str:
        await self.container.upsert(
            {
                "id": checkpoint.checkpoint_id,
                "workflow": self.run_key,
                "workflowName": checkpoint.workflow_name,
                "previous": checkpoint.previous_checkpoint_id,
                "timestamp": checkpoint.timestamp,
                "iteration": checkpoint.iteration_count,
                "data": _pack(checkpoint),
            }
        )
        return checkpoint.checkpoint_id

    async def load(self, checkpoint_id: str) -> WorkflowCheckpoint:
        document = await self.container.read(checkpoint_id, self.run_key)
        if document is None:
            raise WorkflowCheckpointException(f"No checkpoint found with ID {checkpoint_id}")
        return _unpack(document["data"])

    async def _documents(self, workflow_name: str) -> list[dict[str, Any]]:
        documents = await self.container.query(self.run_key)
        return [d for d in documents if d.get("workflowName") == workflow_name]

    async def list_checkpoints(self, *, workflow_name: str) -> list[WorkflowCheckpoint]:
        return [_unpack(d["data"]) for d in await self._documents(workflow_name)]

    async def list_checkpoint_ids(self, *, workflow_name: str) -> list[str]:
        return [d["id"] for d in await self._documents(workflow_name)]

    async def delete(self, checkpoint_id: str) -> bool:
        existed = await self.container.read(checkpoint_id, self.run_key) is not None
        await self.container.delete(checkpoint_id, self.run_key)
        return existed

    async def get_latest(self, *, workflow_name: str) -> WorkflowCheckpoint | None:
        documents = await self._documents(workflow_name)
        if not documents:
            return None
        # The newest is the one no other checkpoint names as its previous; timestamps break any tie.
        named = {d.get("previous") for d in documents}
        tips = [d for d in documents if d["id"] not in named] or documents
        return _unpack(max(tips, key=lambda d: (d.get("iteration", 0), d["timestamp"]))["data"])

    async def clear(self) -> None:
        """Forget this investigation's checkpoints, once it has finished."""
        for document in await self.container.query(self.run_key):
            await self.container.delete(document["id"], self.run_key)
