"""Front Room's room server: phones join, screens connect, and goals are turned into cues for every screen.

    uv run uvicorn frontroom_agents.server.app:app --port 8787

Without FRONTROOM_LIVE=1 every agent uses its rule-based version, so the server runs with no cloud access.

It also serves the Room Director over A2A at /a2a/director and the studio tools over MCP at /mcp.

Rooms, the fairness ledger, the as-run log and investigation checkpoints are kept in Azure Cosmos DB when
FRONTROOM_COSMOS_* is set (in memory otherwise); on start the server restores its rooms and finishes any
investigation it was in the middle of. What fans type is checked by Azure AI Content Safety first.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from a2a.server.routes.fastapi_routes import add_a2a_routes_to_fastapi
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import llm, safety, telemetry
from ..a2a import director_agent
from ..mcp import studio
from ..origins.roles import ModelHypothesizer, ModelSkeptic, ModelWriter
from ..origins.workflow import Team
from ..personal.agent import ModelScorer, PersonalAgent, RuleScorer, Scorer
from ..personal.profiler import ModelProfiler, Profiler, RuleProfiler
from ..store import Store, memory_containers, open_store
from . import eventhub_ingest, speech
from .demo_source import DEMO_FANS, demo_source
from .hub import Hub
from .show import Show, phone_cue_hooks


@dataclass
class Services:
    profiler: Profiler = field(default_factory=RuleProfiler)
    scorer: Scorer = field(default_factory=RuleScorer)
    team: Team = field(default_factory=Team)
    store: Store = field(default_factory=lambda: Store(memory_containers()))


hub = Hub()
shows: dict[str, Show] = {}
services = Services()
telemetry.setup()
studio.context.shows = shows


background: set[asyncio.Task] = set()
"""Investigations being resumed after a restart; kept so they aren't garbage-collected mid-run."""


async def restore() -> None:
    """Rebuilds the rooms the store kept, then finishes, from their checkpoints, the investigations that a
    previous run of the server stopped in the middle of."""
    for document in await services.store.rooms():
        shows[document["room"]] = Show.restore(document, demo_source(), hub, services.team, services.store)
    for run_key in await services.store.unfinished():
        room, shot_id = run_key.split("/", 1)
        task = asyncio.create_task(show_for(room).resume(shot_id))
        background.add(task)
        task.add_done_callback(background.discard)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with studio.http.serving(), open_store() as store:
        services.store = store
        if not llm.live():
            await restore()
            yield
            return
        async with llm.credential() as cred:
            client = llm.chat_client(cred)
            # Profiling one sentence and scoring three offers per fan: the small model is enough.
            fast = llm.chat_client(cred, fast=True)
            services.profiler = ModelProfiler(fast)
            services.scorer = ModelScorer(fast)
            services.team = Team(ModelHypothesizer(client), ModelSkeptic(client), ModelWriter(client))
            studio.context.team = services.team
            await restore()
            yield


@asynccontextmanager
async def lifespan_with_feed(app_: FastAPI):
    """The server's lifespan, plus following the live match feed when FRONTROOM_INGEST=eventhubs."""
    async with lifespan(app_), eventhub_ingest.following_the_feed(goal_in_every_room):
        yield


app = FastAPI(title="Front Room", lifespan=lifespan_with_feed)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

card_routes, rpc_routes = director_agent.routes()
add_a2a_routes_to_fastapi(app, agent_card_routes=card_routes, jsonrpc_routes=rpc_routes)
app.mount("/mcp", studio.http)


# Limits that keep one public deployment from being run out of memory or model budget by anyone.
MAX_ROOMS = 200
MAX_FANS_PER_ROOM = 8
ID = r"^[a-z0-9-]{1,32}$"
fan_tokens: dict[tuple[str, str], str] = {}
"""(room, fan) -> the secret a fan's phone presents to receive its private cues."""


def show_for(room: str) -> Show:
    if not re.fullmatch(ID, room):
        raise HTTPException(status_code=400, detail="room ids are 1-32 lowercase letters, digits or dashes")
    if room not in shows:
        if len(shows) >= MAX_ROOMS:
            # The oldest room goes first; rooms are a match night long, not forever.
            oldest = next(iter(shows))
            del shows[oldest]
            hub.rooms.pop(oldest, None)
        shows[room] = Show(room, demo_source(), hub, agents=[], team=services.team, store=services.store)
    return shows[room]


class Join(BaseModel):
    fan: str = Field(pattern=ID)
    told: str = Field(max_length=400)


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "live": llm.live(),
        "models": llm.provider(),
        "store": services.store.kind,
        "contentSafety": safety.configured(),
    }


@app.post("/rooms/{room}/fans")
async def join(room: str, body: Join) -> dict:
    """A phone joins. The text becomes a profile on this side; the room only learns that a fan joined."""
    show = show_for(room)
    if body.fan not in {a.agent_id for a in show.agents} and len(show.agents) >= MAX_FANS_PER_ROOM:
        raise HTTPException(status_code=409, detail=f"a room holds at most {MAX_FANS_PER_ROOM} phones")
    checked = await safety.check(body.told)
    if not checked.allowed:
        raise HTTPException(status_code=422, detail=checked.message)
    profile = await services.profiler.profile(body.told)
    show.join(PersonalAgent(body.fan, profile, services.scorer))
    await show.save()
    token = fan_tokens[(room, body.fan)] = secrets.token_urlsafe(16)
    await hub.broadcast(
        room,
        {
            "type": "joined",
            "fans": [a.agent_id for a in show.agents],
            "bothClubs": len(show.clubs_present) > 1,
        },
    )
    return {"understood": profile.model_dump(), "token": token, "safetyChecked": checked.checked}


class More(BaseModel):
    token: str = Field(max_length=64)
    told: str = Field(max_length=200)


@app.post("/rooms/{room}/fans/{fan}/more")
async def more_like_this(room: str, fan: str, body: More) -> dict:
    """The phone's "more like this": a fan tells their own helper what they'd like more of. Only the
    helper hears it; the room learns nothing until the helper's next asks."""
    expected = fan_tokens.get((room, fan))
    if not expected or not secrets.compare_digest(body.token, expected):
        raise HTTPException(status_code=403, detail="this phone hasn't joined the room")
    checked = await safety.check(body.told)
    if not checked.allowed:
        raise HTTPException(status_code=422, detail=checked.message)
    agent = next(a for a in show_for(room).agents if a.agent_id == fan)
    likes = [*agent.profile.likes, body.told.strip()][-5:]
    agent.profile = agent.profile.model_copy(update={"likes": likes})
    return {"likes": likes, "safetyChecked": checked.checked}


@app.post("/rooms/{room}/demo")
async def demo(room: str, without: str | None = None) -> dict:
    """Fills the room with the four demo fans, each joining with their own words. `?without=ana` leaves one
    of them out (she has gone to make tea), so the demo can show how the room decides without her."""
    shows.pop(room, None)
    fans = {fan: told for fan, told in DEMO_FANS.items() if fan != without}
    joined = await asyncio.gather(*(join(room, Join(fan=fan, told=told)) for fan, told in fans.items()))
    return dict(zip(fans, joined, strict=True))


@app.post("/rooms/{room}/goals/featured")
async def featured_goal(room: str) -> dict:
    """The goal the demo story is about: Okafor's, after Mensah's press."""
    return await goal(room, show_for(room).source.featured)


@app.post("/rooms/{room}/goals/{index}")
async def goal(room: str, index: int = 0) -> dict:
    """The producer arms the goal's cues. In the demo this is the studio's Arm button."""
    show = show_for(room)
    if not 0 <= index < len(show.source.goals):
        raise HTTPException(status_code=404, detail="no such goal in this match")
    target = show.source.goals[index]
    round_ = await show.goal(target, tv_pts=target.pts + 4_000)
    return {"winner": round_.decision.winner, "dropped": round_.dropped}


@app.websocket("/rooms/{room}/ws")
async def screen(
    socket: WebSocket, room: str, screen: str, fan: str | None = None, token: str | None = None
) -> None:
    """One socket per screen: `?screen=tv|room|studio|demo`, or `?screen=phone&fan=rob&token=…`.

    A phone's cues are private, so a phone socket must present the token its fan was given on joining.
    """
    if screen not in {"tv", "room", "studio", "demo", "phone"} or not re.fullmatch(ID, room):
        await socket.close(code=4400)
        return
    if screen == "phone":
        expected = fan_tokens.get((room, fan or ""))
        if not fan or not token or not expected or not secrets.compare_digest(token, expected):
            await socket.close(code=4403)
            return
    name = f"phone:{fan}" if screen == "phone" else screen
    await socket.accept()
    hub.join(room, name, socket)
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        hub.leave(room, name, socket)


async def goal_in_every_room(index: int) -> None:
    """A goal from the live feed: every room with fans in it gets the same flow as the Arm button."""
    rooms = [show for show in list(shows.values()) if show.agents]
    await asyncio.gather(
        *(show.goal(show.source.goals[index], tv_pts=show.source.goals[index].pts + 4_000) for show in rooms),
        return_exceptions=True,
    )


@app.get("/ingest")
async def ingest() -> dict:
    """What the live feed has delivered so far, if the server follows one."""
    current = eventhub_ingest.current
    return current.status() if current else {"following": None}


# Described audio for the fans who listen (Azure AI Speech), when the Speech key is configured.
narrator = speech.narrator_from_env()


def described_audio(room: str, agent: PersonalAgent, cue: dict) -> None:
    if narrator:
        narrator.attach(room, agent, cue, fan_tokens.get((room, agent.agent_id)))


phone_cue_hooks.append(described_audio)


@app.get("/rooms/{room}/audio/{clip}.mp3")
async def audio(room: str, clip: str, fan: str, token: str) -> Response:
    """A listening fan's spoken story. Private like the phone's cue: it needs that fan's token."""
    expected = fan_tokens.get((room, fan))
    if not narrator or not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403)
    if not narrator.allowed(room, clip, fan):
        raise HTTPException(status_code=404)
    mp3 = await narrator.audio(clip)
    if mp3 is None:
        raise HTTPException(status_code=404)
    return Response(mp3, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})


# Deployed, the same server also serves the built web app. Every surface is a client-side route
# (/tv, /phones, /room, ...), so any GET that isn't an API route or a file gets the app's index.html.
WEB_DIST = Path(os.environ.get("FRONTROOM_WEB_DIST", Path(__file__).parents[3] / "apps" / "web" / "dist"))

if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def web(path: str) -> FileResponse:
        if path.startswith(("rooms/", "a2a/", "mcp")):
            raise HTTPException(status_code=404)
        file = (WEB_DIST / path).resolve()
        if path and file.is_file() and WEB_DIST.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(WEB_DIST / "index.html")
