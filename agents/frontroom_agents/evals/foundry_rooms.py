"""Play one goal into one room on the real room-server code, with every agent on the Foundry project's models,
and keep what each screen received, in order. Shared by the Foundry evaluation and the red team.

The goal comes from the engine's demo match (the server's own copy). The fans join exactly as phones do: a
profiler agent turns what they say into a private profile, and a personal agent bids for them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..foundry.settings import chat_client, settings
from ..origins.roles import Copy, Hypotheses, ModelHypothesizer, ModelSkeptic, ModelWriter, Story
from ..origins.workflow import Team
from ..personal.agent import ModelScorer, PersonalAgent
from ..personal.profiler import ModelProfiler
from ..server.demo_source import demo_source
from ..server.hub import Hub
from ..server.show import Goal, MatchSource, Show

QUERY = "Write the TV lower third, in English and Spanish, for this goal, using only the verified facts."


@dataclass
class RecordingHub(Hub):
    """A hub with no sockets that remembers every message, so a test can see who heard what, and when."""

    sent: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def send(self, room: str, screen: str, message: dict[str, Any]) -> None:
        self.sent.append((screen, message))


@dataclass
class Seen:
    """What the investigation's agents were handed, so a row can show the evidence behind the words."""

    chain: list[dict] = field(default_factory=list)
    story: Story | None = None


@dataclass
class Recording:
    """Wraps the hypothesis agent and the writer to keep their inputs; their outputs are untouched."""

    hypothesizer: ModelHypothesizer
    writer: ModelWriter
    seen: Seen = field(default_factory=Seen)

    async def propose(self, chain: list[dict]) -> Hypotheses:
        self.seen.chain = chain
        return await self.hypothesizer.propose(chain)

    async def write(self, story: Story, feedback: list[str] | None = None) -> Copy:
        self.seen.story = story
        return await self.writer.write(story, feedback)


@dataclass
class Agents:
    """The model-backed roles: the investigation team on the full model, the fans' agents on the fast one."""

    recording: Recording
    skeptic: ModelSkeptic
    profiler: ModelProfiler
    scorer: ModelScorer

    @property
    def team(self) -> Team:
        return Team(self.recording, self.skeptic, self.recording)

    @classmethod
    def on_foundry(cls) -> Agents:
        s = settings()
        full, fast = chat_client(s.model), chat_client(s.model_fast)
        recording = Recording(ModelHypothesizer(full), ModelWriter(full))
        return cls(recording, ModelSkeptic(full), ModelProfiler(fast), ModelScorer(fast))


def _context(seen: Seen) -> str:
    """What the writer was allowed to know: the verified facts, and the move as the event feed logged it."""
    moves = "; ".join(f"{e.get('playerName') or e.get('playerId')} {e['type']}" for e in seen.chain)
    facts = json.dumps(vars(seen.story)) if seen.story else "{}"
    return f"Verified facts: {facts}. The move, from the event feed: {moves}."


def _tv_text(cue: dict) -> str:
    f = cue["fields"]
    provenance = f"{f['asked']} of {f['inRoom']} in the room asked for this"
    neutral = " Kept neutral: both clubs are here" if f["neutral"] else ""
    return f"{f['headline']} {f['line']} {provenance}.{neutral}"


async def play(
    room: str, fans: dict[str, str], goal: Goal, agents: Agents, source: MatchSource | None = None
) -> dict[str, Any]:
    """One goal in one room. Returns an evaluation row: the writer's words and context, and every screen."""
    source = source or demo_source()
    agents.recording.seen = Seen()
    hub = RecordingHub()
    joined = [
        PersonalAgent(fan, await agents.profiler.profile(told), agents.scorer) for fan, told in fans.items()
    ]
    show = Show(room=room, source=source, hub=hub, agents=joined, team=agents.team)
    round_ = await show.goal(goal, tv_pts=goal.pts + 4_000)

    case_message = next(m for _, m in hub.sent if m["type"] == "insight")
    decision = next(m for _, m in hub.sent if m["type"] == "decision")
    partisan = {b["candidateId"]: b["partisan"] for b in decision["bids"]}
    cues = [(i, screen, m["cue"]) for i, (screen, m) in enumerate(hub.sent) if m["type"] == "cue"]
    tv = next((c for _, s, c in cues if s == "tv"), None)
    winner = round_.decision.winner or ""
    copy = case_message["copy"]
    return {
        "room": room,
        "goal": goal.shot_id,
        "query": QUERY,
        "context": _context(agents.recording.seen),
        "response": (
            f"EN: {copy['en_headline']}. {copy['en_line']}\nES: {copy['es_headline']}. {copy['es_line']}"
        ),
        "copy": copy,
        "story": vars(agents.recording.seen.story) if agents.recording.seen.story else {},
        "roster": sorted(set(source.players.values())),
        "fans": fans,
        "profiles": {a.agent_id: a.profile.model_dump() for a in joined},
        "both_clubs": len(show.clubs_present) > 1,
        "winner": winner,
        "winner_partisan": bool(partisan.get(winner, False)),
        "tv_text": _tv_text(tv) if tv else "",
        "phone_texts": [f"{c['fields']['headline']} {c['fields']['line']}" for _, s, c in cues if s != "tv"],
        "sends": [
            {"screen": s, "order": i, "pts": c["pts"], "on_tv": bool(c["fields"].get("onTv", s == "tv"))}
            for i, s, c in cues
        ],
        "trace": [f"{step['role']}: {step['summary']}" for step in case_message["trace"]],
    }
