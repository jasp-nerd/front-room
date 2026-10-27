"""A room watching a match: what happens, screen by screen, when a goal goes in.

1. The studio sees the investigation start and every step of its trace.
2. The investigation's insight becomes the neutral "where it started" offer, next to one offer that favours
   each club. The studio arms them for every room.
3. The room's personal agents bid, the Director decides, and the room view gets the full ledger.
4. The TV gets the winning lower third. Every phone gets either the TV's choice in its own language, or the
   fan's own pick if that lost.

The match source, the agents and the clock are passed in, so tests can run a whole goal in milliseconds.

Everything the room may know is kept in the store (Azure Cosmos DB when deployed): who is in the room and how
long each fan has waited, every decision in the fairness ledger, every cue in the as-run log, and a
checkpoint of the investigation after each step. A restarted server rebuilds its rooms from the store and
finishes any investigation it was in the middle of, from its last checkpoint.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..a2a.remote import director_from_env
from ..origins.workflow import Case, Request, Team, investigate, to_insight
from ..personal.agent import Offer, PersonalAgent
from ..room.director import Candidate, RoomState
from ..room.session import Round, run_round
from ..room.wire import decision_to_wire
from ..store import Store, memory_containers
from ..telemetry import span
from .hub import Hub

DWELL_MS = 8_000
CLUB_NAMES = {"kestrel": "Kestrel", "ashvale": "Ashvale"}

phone_cue_hooks: list[Callable[[str, PersonalAgent, dict], None]] = []
"""Called with (room, agent, cue) just before each phone cue is sent; the server adds described audio here."""


@dataclass(frozen=True)
class Goal:
    shot_id: str
    pts: int
    """When the goal is on the TV, in milliseconds from kick-off of the stream."""
    scoring_club: str
    conceding_club: str
    attacking_right: bool


@dataclass(frozen=True)
class MatchSource:
    match_id: str
    events: list[dict]
    players: dict[str, str]
    goals: list[Goal]
    featured: int = 0
    """Which goal the demo arms: the one the story is about."""


@dataclass
class Fairness:
    """How long each fan has gone without their pick on the TV. Feeds the Director's fairness weights."""

    since_pick: dict[str, float] = field(default_factory=dict)

    def seconds(self, now: float) -> dict[str, float]:
        return {fan: now - since for fan, since in self.since_pick.items()}

    def picked(self, fans: list[str], now: float) -> None:
        for fan in fans:
            self.since_pick[fan] = now

    def joined(self, fan: str, now: float) -> None:
        """Waiting starts when a fan joins, so joining late (or rejoining under a new name) earns nothing."""
        self.since_pick[fan] = now

    def left(self, fan: str) -> None:
        self.since_pick.pop(fan, None)

    def waited(self, now: float) -> dict[str, float]:
        """Seconds each fan has waited, which survives a restart where monotonic clock readings don't."""
        return {fan: round(now - since, 3) for fan, since in self.since_pick.items()}

    @classmethod
    def restored(cls, waited: dict[str, float], saved_at: float, now: float) -> Fairness:
        # The server was down for (wall clock now - saved_at): that time counts as waiting too.
        down = max(time.time() - saved_at, 0.0)
        return cls({fan: now - seconds - down for fan, seconds in waited.items()})


def offers_for(goal: Goal, insight: dict, followed: set[str] = frozenset()) -> list[Offer]:
    """What the room could put on the TV after a goal. A card about the scorer is offered only when someone in
    the room follows them; it favours the scorer's club, so the house rules treat it as one-sided."""
    scoring, conceding = CLUB_NAMES[goal.scoring_club], CLUB_NAMES[goal.conceding_club]
    scorer = next((f["value"] for f in insight.get("facts", []) if f["key"] == "scorer"), None)
    player_card = (
        [
            Offer(
                Candidate(f"player-{str(scorer).lower()}", goal.pts, partisan=True),
                f"{scorer} in numbers",
                f"How far and how fast {scorer} ran tonight, and their part in the goal",
                "player",
                favours=goal.scoring_club,  # type: ignore[arg-type]
                player=str(scorer),
            )
        ]
        if scorer in followed
        else []
    )
    return [
        Offer(
            Candidate("where-it-started", goal.pts, partisan=False),
            "Where it started",
            "Where the goal really began, and how the move built",
            "story",
        ),
        Offer(
            Candidate(f"{goal.scoring_club}-pressing-map", goal.pts, partisan=True),
            f"{scoring}'s pressing map",
            f"How {scoring} pressed to win the ball back",
            "tactics",
            favours=goal.scoring_club,
        ),  # type: ignore[arg-type]
        Offer(
            Candidate("keepers-view", goal.pts, partisan=True),
            f"How {conceding}'s keeper saw it",
            "The shot from the goal line",
            "keeper",
            favours=goal.conceding_club,
        ),  # type: ignore[arg-type]
        *player_card,
    ]


def tv_cue(
    case: Case, insight: dict, round_: Round, goal: Goal, asked: int, in_room: int, neutral: bool
) -> dict:
    assert case.copy is not None
    return {
        "cueId": f"cue-tv-{goal.shot_id}",
        "insightId": insight["id"],
        "template": "where-it-started",
        "destination": "room-tv",
        "pts": goal.pts,
        "dwellMs": DWELL_MS,
        "lang": "en",
        "fields": {
            "headline": case.copy.en_headline,
            "line": case.copy.en_line,
            "asked": asked,
            "inRoom": in_room,
            "neutral": neutral,
        },
        "decisionId": f"decision-{goal.shot_id}",
        "state": "on-air",
        "verified": True,
    }


def phone_cue(fan: str, lang: str, case: Case, insight: dict, goal: Goal, overlay: str, on_tv: bool) -> dict:
    assert case.copy is not None
    spanish = lang == "es"
    return {
        "cueId": f"cue-{fan}-{goal.shot_id}",
        "insightId": insight["id"],
        "agentId": fan,
        "template": "where-it-started" if on_tv else "explainer",
        "destination": "phone",
        "pts": goal.pts,
        "dwellMs": DWELL_MS,
        "lang": lang,
        "fields": {
            "overlay": overlay,
            "onTv": on_tv,
            "headline": case.copy.es_headline if spanish else case.copy.en_headline,
            "line": case.copy.es_line if spanish else case.copy.en_line,
        },
        "state": "on-air",
        "verified": True,
    }


@dataclass
class Show:
    room: str
    source: MatchSource
    hub: Hub
    agents: list[PersonalAgent]
    team: Team = field(default_factory=Team)
    fairness: Fairness = field(default_factory=Fairness)
    rounds: list[Round] = field(default_factory=list)
    overlay_ends_at: int | None = None
    """When the TV's current or last overlay ends, in TV time, so the house rules can space overlays out."""
    store: Store = field(default_factory=lambda: Store(memory_containers()))
    investigated: dict[str, Case] = field(default_factory=dict)
    """Investigations finished (or resumed after a restart) whose round has not been played yet, by shot."""
    _one_round_at_a_time: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @classmethod
    def restore(
        cls, document: dict[str, Any], source: MatchSource, hub: Hub, team: Team, store: Store
    ) -> Show:
        """A room as the store kept it: its fairness clock and TV timing. Phones rejoin with their words."""
        return cls(
            document["room"],
            source,
            hub,
            agents=[],
            team=team,
            fairness=Fairness.restored(document.get("waited", {}), document["savedAt"], time.monotonic()),
            overlay_ends_at=document.get("overlayEndsAt"),
            store=store,
        )

    async def save(self) -> None:
        await self.store.save_room(
            self.room,
            [a.agent_id for a in self.agents],
            len(self.clubs_present) > 1,
            self.fairness.waited(time.monotonic()),
            self.overlay_ends_at,
        )

    def _run_key(self, shot_id: str) -> str:
        return f"{self.room}/{shot_id}"

    async def _investigate(self, goal: Goal) -> Case:
        """The goal's investigation, checkpointed after every step. If it was resumed after a restart, that
        result is used; if a checkpoint of it is waiting, it is finished from there, not started again."""
        if goal.shot_id in self.investigated:
            return self.investigated.pop(goal.shot_id)
        request = Request(
            self.source.match_id,
            goal.shot_id,
            goal.pts,
            self.source.events,
            self.source.players,
            goal.attacking_right,
        )

        async def step(role: str, done) -> None:
            message = {"type": "step", "role": role, "state": "done" if done else "working"}
            if done:
                message |= {"summary": done.summary, "ms": done.ms}
            await self.hub.broadcast(self.room, message, ("studio", "room", "demo"))

        checkpoints = self.store.checkpoints(self._run_key(goal.shot_id))
        return await investigate(request, self.team, on_step=step, checkpoints=checkpoints)

    async def resume(self, shot_id: str) -> Case | None:
        """Finishes an investigation the server was in the middle of when it stopped, from its checkpoint.
        Its round is played when the goal is next armed."""
        goal = next((g for g in self.source.goals if g.shot_id == shot_id), None)
        if goal is None:
            await self.store.checkpoints(self._run_key(shot_id)).clear()
            return None
        async with self._one_round_at_a_time:
            await self.hub.broadcast(
                self.room,
                {"type": "investigating", "shotId": shot_id, "resumed": True},
                ("studio", "room", "demo"),
            )
            with span("investigation.resume", room=self.room, shot=shot_id):
                case = await self._investigate(goal)
            self.investigated[shot_id] = case
            return case

    @property
    def clubs_present(self) -> set[str]:
        return {a.profile.club for a in self.agents if a.profile.club}

    def join(self, agent: PersonalAgent) -> None:
        self.agents = [a for a in self.agents if a.agent_id != agent.agent_id] + [agent]
        self.fairness.joined(agent.agent_id, time.monotonic())

    async def goal(self, goal: Goal, tv_pts: int) -> Round:
        # A double-pressed Arm must not run two investigations and two rounds over each other.
        async with self._one_round_at_a_time:
            return await self._goal(goal, tv_pts)

    async def _goal(self, goal: Goal, tv_pts: int) -> Round:
        # The round works on the room as it was when the goal went in, even if a phone joins meanwhile.
        agents = list(self.agents)
        await self.hub.broadcast(
            self.room, {"type": "investigating", "shotId": goal.shot_id}, ("studio", "room", "demo")
        )
        case = await self._investigate(goal)
        insight = to_insight(case)
        await self.hub.broadcast(
            self.room,
            {
                "type": "insight",
                "insight": insight,
                "copy": vars(case.copy),
                "trace": [vars(s) for s in case.trace],
            },
            ("studio", "room", "demo"),
        )

        offers = offers_for(goal, insight, {p for a in agents for p in a.profile.players})
        fans = [a.agent_id for a in agents]
        now = time.monotonic()
        on_air = self.overlay_ends_at is not None and tv_pts < self.overlay_ends_at
        state = RoomState(
            agent_ids=fans,
            both_clubs_present=len({a.profile.club for a in agents if a.profile.club}) > 1,
            tv_pts=tv_pts,
            overlay_on_air=on_air,
            last_overlay_end_pts=None if on_air else self.overlay_ends_at,
            seconds_without_screen=self.fairness.seconds(now),
        )
        with span(
            "room.decide", room=self.room, fans=len(fans), both_clubs=state.both_clubs_present
        ) as traced:
            director = director_from_env(self.room)
            round_ = await run_round(agents, offers, state, director=director)
            traced.set_attribute("frontroom.director", director.used if director else "local")
            traced.set_attribute("frontroom.winner", round_.decision.winner or "")
            traced.set_attribute("frontroom.dropped", len(round_.dropped))
            traced.set_attribute(
                "frontroom.struck",
                ",".join(c.candidate_id for c in round_.decision.candidates if c.struck_by),
            )
        reasons = {a.agent_id: dict(a.reasons) for a in agents}
        partisan = {o.candidate.id: o.candidate.partisan for o in offers}
        self.rounds.append(round_)
        winner = round_.decision.winner
        askers = next((list(c.asked_by) for c in round_.decision.candidates if c.won), [])
        self.fairness.picked([f for f, pick in self._favourites(round_).items() if pick == winner], now)

        wire = decision_to_wire(round_.decision, self.room, f"decision-{goal.shot_id}")
        bids = [
            {
                "roomId": self.room,
                "agentId": b.agent_id,
                "candidateId": b.candidate_id,
                "utility": b.utility,
                "partisan": partisan[b.candidate_id],
                "placedAtPts": tv_pts,
            }
            for b in round_.bids
        ]
        await self.hub.broadcast(
            self.room,
            {"type": "decision", "decision": wire, "bids": bids, "dropped": round_.dropped},
            ("room", "studio", "demo"),
        )
        await self.store.record_decision(self.room, wire, bids, round_.dropped)
        if winner:
            cue = tv_cue(case, insight, round_, goal, len(askers), len(fans), state.both_clubs_present)
            await self.hub.send(self.room, "tv", {"type": "cue", "cue": cue})
            await self.store.record_cue(self.room, "tv", cue)
            self.overlay_ends_at = tv_pts + DWELL_MS

        titles = {o.candidate.id: o.title for o in offers}
        private = round_.decision.delivered_privately
        for agent in agents:
            overlay = private.get(agent.agent_id, winner or "")
            cue = phone_cue(
                agent.agent_id,
                agent.profile.language,
                case,
                insight,
                goal,
                overlay,
                on_tv=agent.agent_id not in private,
            )
            cue["fields"]["title"] = titles.get(overlay, "")
            cue["fields"]["tvOverlay"] = winner or ""
            cue["fields"]["reason"] = reasons[agent.agent_id].get(overlay, "")
            for hook in phone_cue_hooks:
                hook(self.room, agent, cue)
            await self.hub.send(self.room, f"phone:{agent.agent_id}", {"type": "cue", "cue": cue})
            await self.store.record_cue(self.room, f"phone:{agent.agent_id}", cue)
        await self.save()
        return round_

    @staticmethod
    def _favourites(round_: Round) -> dict[str, str]:
        best: dict[str, tuple[float, str]] = {}
        for bid in round_.bids:
            if bid.utility > best.get(bid.agent_id, (-1.0, ""))[0]:
                best[bid.agent_id] = (bid.utility, bid.candidate_id)
        return {fan: pick for fan, (_, pick) in best.items()}
