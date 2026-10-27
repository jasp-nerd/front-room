"""Calling the Room Director over A2A, from the personal agents' side of the trust boundary.

A room round can decide locally (the default: same process, no network) or ask a Director that runs
somewhere else, for example the broadcaster's, with RemoteDirector. Both give the same answer for the
same round, which the tests check.
"""

from __future__ import annotations

import os
import uuid

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers.proto_helpers import get_data_parts, new_data_message
from a2a.types import AgentCard, Role, SendMessageRequest

from ..room.director import Bid, Candidate, Decision, RoomState
from ..room.session import FallbackDirector
from ..room.wire import decision_from_wire, round_to_wire
from .director_agent import CARD_PATH


class RemoteDirector:
    """A Director reached over A2A. Pass an AgentCard, or a base URL to fetch the card from."""

    def __init__(self, agent: AgentCard | str, http: httpx.AsyncClient | None = None, room_id: str = "room"):
        self._agent = agent
        self._http = http
        self._room_id = room_id

    async def _card(self, http: httpx.AsyncClient) -> AgentCard:
        if isinstance(self._agent, AgentCard):
            return self._agent
        resolver = A2ACardResolver(http, self._agent, agent_card_path=CARD_PATH)
        return await resolver.get_agent_card()

    async def decide(self, candidates: list[Candidate], bids: list[Bid], state: RoomState) -> Decision:
        http = self._http or httpx.AsyncClient(timeout=10)
        try:
            config = ClientConfig(httpx_client=http, streaming=False)
            client = await create_client(await self._card(http), config)
            message = new_data_message(
                round_to_wire(candidates, bids, state, self._room_id), role=Role.ROLE_USER
            )
            message.message_id = str(uuid.uuid4())
            async for response in client.send_message(SendMessageRequest(message=message)):
                for part in get_data_parts(response.message.parts):
                    if isinstance(part, dict) and "candidates" in part:
                        return decision_from_wire(part)
        finally:
            if self._http is None:
                await http.aclose()
        raise RuntimeError("the Director answered without a decision")


def director_from_env(room_id: str) -> FallbackDirector | None:
    """The room's Director over A2A when FRONTROOM_DIRECTOR_URL is set (deployed: the broadcaster's Director
    at /a2a/director/), with the same rules in-process as the fallback. None: decide in-process."""
    url = os.environ.get("FRONTROOM_DIRECTOR_URL")
    return FallbackDirector(RemoteDirector(url, room_id=room_id)) if url else None
