"""The Room Director as an A2A agent.

Personal agents belong to the fans: each one runs for one phone and holds that fan's private profile. The
Director belongs to the broadcaster and decides what the shared TV shows. A2A is the contract across that
trust boundary. A personal agent sends only numbers (its bids for this round's overlays); the Director
answers with the decision and its ledger. Profiles, reasons and anything else a fan said never cross.

Served by the room server at /a2a/director (agent card at /a2a/director/.well-known/agent-card.json).
"""

from __future__ import annotations

import os

from a2a.helpers.proto_helpers import get_data_parts, new_data_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentProvider, AgentSkill, Role
from starlette.routing import BaseRoute

from ..room.director import BID_BUDGET, FAIRNESS_MAX_BONUS, MIN_GAP_MS, decide
from ..room.wire import decision_to_wire, round_from_wire

PATH = "/a2a/director"
CARD_PATH = f"{PATH}/.well-known/agent-card.json"

SKILL = AgentSkill(
    id="decide-shared-screen",
    name="Decide what the shared TV shows",
    description=(
        "Send one round: the overlays that could go on the room's TV, every personal agent's bids for "
        "them (numbers only, no profiles) and the room's facts. The Director strikes overlays that break a "
        "house rule (one club's framing while both clubs are in the room, a VAR check, less than "
        f"{MIN_GAP_MS // 1000} s since the last overlay, anything not yet on this TV), scales each agent's "
        f"bids to a budget of {BID_BUDGET:g}, weights fans who have waited longer by up to "
        f"{1 + FAIRNESS_MAX_BONUS:g} times, and returns the decision as protocol JSON: the winner, every "
        "score, the rule that struck each loser, and which fans get their pick on their phone instead. "
        "The same round always gets the same answer."
    ),
    tags=["fairness", "shared screen", "house rules", "deterministic"],
    examples=['{"roomId": "4821", "candidates": [...], "bids": [...], "state": {...}}'],
    input_modes=["application/json"],
    output_modes=["application/json"],
)


def agent_card(base_url: str | None = None) -> AgentCard:
    """The Director's card. The URL is where this server is reachable from personal agents."""
    base = (base_url or os.environ.get("FRONTROOM_PUBLIC_URL", "http://localhost:8787")).rstrip("/")
    return AgentCard(
        name="Front Room Director",
        description="Decides fairly what one living room's shared TV shows when every fan's agent wants "
        "something different. Deterministic and auditable; it never sees fan profiles.",
        version="1.0.0",
        provider=AgentProvider(organization="Front Room", url=base),
        supported_interfaces=[
            AgentInterface(url=f"{base}{PATH}/", protocol_binding="JSONRPC", protocol_version="1.0")
        ],
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[SKILL],
    )


class DirectorExecutor(AgentExecutor):
    """Answers each message with one decision. There is no conversation: a round in, a decision out."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        assert context.message is not None
        rounds = [p for p in get_data_parts(context.message.parts) if isinstance(p, dict)]
        if not rounds:
            raise ValueError("send the round as a JSON data part: {roomId, candidates, bids, state}")
        candidates, bids, state = round_from_wire(rounds[0])
        decision = decide(candidates, bids, state)
        room = str(rounds[0].get("roomId", "room"))
        answer = decision_to_wire(decision, room, f"decision-{room}-{state.tv_pts}")
        await event_queue.enqueue_event(
            new_data_message(
                answer, context_id=context.context_id, task_id=context.task_id, role=Role.ROLE_AGENT
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("a decision takes well under a millisecond; there is nothing to cancel")


def routes(card: AgentCard | None = None) -> tuple[list[BaseRoute], list[BaseRoute]]:
    """The agent card route and the JSON-RPC route, ready for add_a2a_routes_to_fastapi."""
    card = card or agent_card()
    handler = DefaultRequestHandler(
        agent_executor=DirectorExecutor(), task_store=InMemoryTaskStore(), agent_card=card
    )
    return create_agent_card_routes(card, card_url=CARD_PATH), create_jsonrpc_routes(
        handler, rpc_url=f"{PATH}/"
    )
