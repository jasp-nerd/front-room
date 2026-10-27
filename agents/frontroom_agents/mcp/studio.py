"""Studio tools over MCP: what a broadcast studio's assistant can ask Front Room.

A producer's assistant (Copilot, a Foundry agent, any MCP client) can investigate where a goal started, read
how a room decided, or check the fairness evaluation, by calling tools instead of reading screens. The same
answers the studio and room views show, from the same code.

    python -m frontroom_agents.mcp.studio        # stdio, for a local MCP client
    POST {server}/mcp                            # streamable HTTP, mounted on the room server
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from ..origins.workflow import Request, Team, investigate, to_insight
from ..room.wire import decision_to_wire
from ..server.demo_source import demo_source

if TYPE_CHECKING:
    from ..server.show import Show

FAIRNESS_RESULTS = Path(__file__).parents[1] / "evals" / "fairness-results.json"


@dataclass
class StudioContext:
    """What the tools read. The room server shares its live rooms and its agent team here."""

    shows: dict[str, Show] = field(default_factory=dict)
    team: Team = field(default_factory=Team)


context = StudioContext()

studio = MCPServer(
    name="front-room-studio",
    title="Front Room studio tools",
    instructions=(
        "Tools for a football broadcast studio using Front Room. Investigate where a goal started (the "
        "answer is checked against the event feed before it is returned), read how a living room's agents "
        "and its Director decided what its TV showed, and read the fairness evaluation over simulated rooms."
    ),
)


@studio.tool(structured_output=True)
async def investigate_goal(match_id: str, shot_id: str) -> dict[str, Any]:
    """Where did this goal really start? Runs the origins investigation (hypothesis, value model, skeptic,
    verify, writer, fact check) and returns the verified insight, the on-air copy in English and Spanish,
    and every step of the investigation's trace."""
    source = demo_source()
    goal = next((g for g in source.goals if g.shot_id == shot_id), None)
    if source.match_id != match_id or goal is None:
        known = ", ".join(f"{source.match_id}/{g.shot_id}" for g in source.goals)
        raise ValueError(f"no goal {match_id}/{shot_id}; known goals: {known}")
    request = Request(
        source.match_id, goal.shot_id, goal.pts, source.events, source.players, goal.attacking_right
    )
    case = await investigate(request, context.team)
    return {
        "insight": to_insight(case),
        "copy": case.copy.model_dump() if case.copy else None,
        "trace": [vars(step) for step in case.trace],
    }


@studio.tool(structured_output=True)
def room_ledger(room: str) -> dict[str, Any]:
    """How a living room last decided what its shared TV showed: the Director's ledger (scores, the rule
    that struck each overlay, fairness weights, who got their pick on their phone) and any agent that was
    too late to bid. Fan profiles are never part of it."""
    show = context.shows.get(room)
    if show is None or not show.rounds:
        return {"room": room, "decision": None, "dropped": [], "note": "no decision in this room yet"}
    latest = show.rounds[-1]
    return {
        "room": room,
        "decision": decision_to_wire(latest.decision, room, f"decision-{room}-latest"),
        "dropped": latest.dropped,
    }


@studio.tool(structured_output=True)
def fairness_report() -> dict[str, Any]:
    """The Director against a loudest-bid-wins baseline over 10,000 simulated living rooms: neutral-rule
    violations, how well the least-served fan was served, longest waits and fans never served."""
    return json.loads(FAIRNESS_RESULTS.read_text())


class HttpMount:
    """The ASGI app mounted at /mcp. MCP's HTTP session manager can run only once, so every time the room
    server starts (`serving()` in its lifespan) a fresh streamable-HTTP app is built behind this mount."""

    def __init__(self) -> None:
        self._app: Any = None

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if self._app is None:
            raise RuntimeError("the MCP endpoint is not running; enter studio.serving() first")
        await self._app(scope, receive, send)

    @asynccontextmanager
    async def serving(self) -> AsyncIterator[None]:
        # Stateless, and open to any host: the tools hold no secrets and the server sits behind its ingress.
        self._app = studio.streamable_http_app(
            streamable_http_path="/",
            stateless_http=True,
            json_response=True,
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )
        try:
            async with studio.session_manager.run():
                yield
        finally:
            self._app = None


http = HttpMount()


if __name__ == "__main__":
    studio.run("stdio")
