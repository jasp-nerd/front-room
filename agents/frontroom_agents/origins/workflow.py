"""The origins investigation: where did this goal really start, and can we say so on TV?

An Agent Framework workflow in seven steps. Thinking roles propose and argue; deterministic steps measure,
decide and check, so nothing reaches a screen that the event feed and the value model don't support.

    extract -> hypothesis -> experiment -> skeptic -> verify -> writer -> check

- extract (rules): the scoring team's possession, from the regain to the shot.
- hypothesis (model): up to three actions where the goal could have started.
- experiment (value model): each action's value against typical play, with a 90% interval.
- skeptic (model): argues with the evidence and recommends decisive or shared.
- verify (rules): applies the decisive rule. The rule wins over the skeptic; disagreements are recorded.
- writer (model): the lower third in English and Spanish, from the verified facts only.
- check (rules): every name and figure in the copy must be in the facts, or the copy is replaced.
"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from typing import Any, Never

from agent_framework import (
    CheckpointStorage,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    register_checkpoint_type,
)

from .chain import SHOTS, Credit, Verdict, credit, scoring_possession, verdict
from .roles import (
    LIMITS,
    NUMBER_WORDS,
    NUMBER_WORDS_ES,
    Copy,
    Hypotheses,
    Hypothesis,
    Hypothesizer,
    Review,
    RuleHypothesizer,
    RuleSkeptic,
    RuleWriter,
    Skeptic,
    Story,
    Writer,
)
from .xt import ExpectedThreat


@dataclass(frozen=True)
class Request:
    match_id: str
    shot_id: str
    pts: int
    events: list[dict]
    players: dict[str, str]
    """Player id to the name used on air."""
    attacking_right: bool


@dataclass(frozen=True)
class Step:
    role: str
    summary: str
    ms: float


@dataclass
class Case:
    """Everything the investigation found, passed from step to step and kept as its trace."""

    request: Request
    chain: list[dict] = field(default_factory=list)
    hypotheses: Hypotheses | None = None
    credits: list[Credit] = field(default_factory=list)
    review: Review | None = None
    verdict: Verdict | None = None
    story: Story | None = None
    copy: Copy | None = None
    trace: list[Step] = field(default_factory=list)

    def label(self, event_id: str) -> str:
        """An action as people say it: "Mensah's press" rather than its event id."""
        event = next((e for e in self.chain if e["id"] == event_id), None)
        if not event:
            return event_id
        action = ACTION_WORDS.get(event["type"], event["type"].replace("_", " "))
        return f"{event.get('playerName') or event.get('playerId')}'s {action}"


@dataclass(frozen=True)
class Team:
    hypothesizer: Hypothesizer = field(default_factory=RuleHypothesizer)
    skeptic: Skeptic = field(default_factory=RuleSkeptic)
    writer: Writer = field(default_factory=RuleWriter)


async def _timed[T](
    case: Case, role: str, run: Callable[[], Awaitable[T]], fallback: Callable[[], Awaitable[T]]
) -> T:
    """Runs one role, falling back to its rule-based version if the model call fails, and records the step."""
    started = time.perf_counter()
    note = ""
    try:
        result = await run()
    except Exception as error:
        result = await fallback()
        note = f" (model unavailable: {type(error).__name__}; used the rule-based {role})"
    case.trace.append(Step(role, _summarise(result) + note, round((time.perf_counter() - started) * 1000, 1)))
    return result


def _summarise(result: Any) -> str:
    if isinstance(result, Hypotheses):
        return "; ".join(f"{h.event_id}: {h.reason}" for h in result.items)
    if isinstance(result, Review):
        return f"{result.recommendation}. " + " ".join(result.objections)
    if isinstance(result, Copy):
        return f"{result.en_headline} / {result.es_headline}"
    return str(result)


# Actions as a commentator names them: the feed's "dribble" is a carry with the ball, a run on air.
ACTION_WORDS = {
    "press": "press",
    "tackle": "tackle",
    "interception": "interception",
    "pass": "pass",
    "dribble": "run",
    "take_on": "take-on",
    "cross": "cross",
    "throw_in": "throw-in",
    "free_kick": "free kick",
    "corner": "corner",
    "goal_kick": "goal kick",
}


def _where(x_attacking: float) -> str:
    if x_attacking < 40:
        return "deep in their own half"
    if x_attacking < 65:
        return "on halfway"
    if x_attacking < 88:
        return "in the final third"
    return "in the box"


class Extract(Executor):
    @handler
    async def run(self, request: Request, ctx: WorkflowContext[Case]) -> None:
        case = Case(request)
        case.chain = [
            {**e, "playerName": request.players.get(e.get("playerId", ""), "")}
            for e in scoring_possession(request.events, request.shot_id)
        ]
        case.trace.append(
            Step("extract", f"{len(case.chain)} actions, from {case.label(case.chain[0]['id'])}", 0.0)
        )
        await ctx.send_message(case)


class Hypothesise(Executor):
    def __init__(self, team: Team):
        super().__init__(id="hypothesis")
        self.team = team

    @handler
    async def run(self, case: Case, ctx: WorkflowContext[Case]) -> None:
        known = {e["id"] for e in case.chain}
        proposed = await _timed(
            case,
            "hypothesis",
            lambda: self.team.hypothesizer.propose(case.chain),
            lambda: RuleHypothesizer().propose(case.chain),
        )
        proposed.items = [h for h in proposed.items if h.event_id in known]
        case.hypotheses = proposed
        named = "; ".join(f"{case.label(h.event_id)}: {h.reason}" for h in proposed.items)
        previous = case.trace[-1].summary
        fallback_note = (
            previous[previous.index(" (model unavailable") :] if "(model unavailable" in previous else ""
        )
        case.trace[-1] = replace(case.trace[-1], summary=named + fallback_note)
        await ctx.send_message(case)


class Experiment(Executor):
    def __init__(self, model: ExpectedThreat):
        super().__init__(id="experiment")
        self.model = model

    @handler
    async def run(self, case: Case, ctx: WorkflowContext[Case]) -> None:
        started = time.perf_counter()
        case.credits = credit(case.chain, self.model, case.request.attacking_right)
        summary = "; ".join(
            f"{case.label(c.event_id)} {c.value:+.3f} ({c.low:+.3f} to {c.high:+.3f})" for c in case.credits
        )
        case.trace.append(Step("experiment", summary, round((time.perf_counter() - started) * 1000, 1)))
        await ctx.send_message(case)


class Scrutinise(Executor):
    def __init__(self, team: Team):
        super().__init__(id="skeptic")
        self.team = team

    @handler
    async def run(self, case: Case, ctx: WorkflowContext[Case]) -> None:
        assert case.hypotheses is not None
        hypotheses, credits = case.hypotheses, [c for c in case.credits if c.type not in SHOTS]
        names = {c.event_id: case.label(c.event_id) for c in case.credits}
        case.review = await _timed(
            case,
            "skeptic",
            lambda: self.team.skeptic.review(hypotheses, credits, names),
            lambda: RuleSkeptic().review(hypotheses, credits, names),
        )
        await ctx.send_message(case)


# What the TV may claim. Graded against the simulator's ground truth (evals/origins.py, engine/ORACLE.md), a
# "this action decided it" verdict from the value model was right about 1 time in 20 on unseen matches, at
# any threshold we tried. So the shared screen states only what the event feed proves: where the move
# started, the passes and the scorer. The measured verdict is still recorded in the insight, as a model
# estimate for analysts and the studio, and never reaches the TV as a fact.
DECISIVE_ON_AIR = False


class Verify(Executor):
    @handler
    async def run(self, case: Case, ctx: WorkflowContext[Case]) -> None:
        case.verdict = verdict(case.credits)
        names = case.request.players
        origin = case.chain[0]
        top = case.verdict.top
        x = origin["start"]["x"] if case.request.attacking_right else 105 - origin["start"]["x"]
        shot = case.chain[-1]
        case.story = Story(
            verdict=case.verdict.kind if DECISIVE_ON_AIR else "shared",
            origin_player=names.get(origin.get("playerId", ""), ""),
            origin_action=ACTION_WORDS.get(origin["type"], origin["type"]),
            origin_where=_where(x),
            passes=sum(1 for e in case.chain if e["type"] == "pass"),
            scorer=names.get(shot.get("playerId", ""), ""),
            credited_player=names.get(top.player_id or "", ""),
            credited_action=ACTION_WORDS.get(top.type, top.type),
        )
        agrees = case.review is None or case.review.recommendation == case.verdict.kind
        note = "" if agrees else f"; the skeptic recommended {case.review.recommendation}, the rule decides"
        on_air = "" if DECISIVE_ON_AIR else "; on air: only where it started, the passes and the scorer"
        biggest = case.label(top.event_id)
        summary = f"model estimate {case.verdict.kind}, biggest single action {biggest}{note}"
        case.trace.append(Step("verify", summary + on_air, 0.0))
        await ctx.send_message(case)


class Write(Executor):
    def __init__(self, team: Team):
        super().__init__(id="writer")
        self.team = team

    @handler
    async def run(self, case: Case, ctx: WorkflowContext[Case]) -> None:
        assert case.story is not None
        story = case.story
        everyone = set(case.request.players.values())
        case.copy = await _timed(
            case, "writer", lambda: self.team.writer.write(story), lambda: RuleWriter().write(story)
        )
        # One revision: the writer sees exactly what the fact check would reject, and tries again.
        problems = fact_check(case.copy, story, everyone)
        if problems:
            case.copy = await _timed(
                case,
                "writer",
                lambda: self.team.writer.write(story, feedback=problems),
                lambda: RuleWriter().write(story),
            )
            first = case.trace[-1]
            case.trace[-1] = replace(
                first, summary=f"revised after: {'; '.join(problems)}. Now: {first.summary}"
            )
        await ctx.send_message(case)


# Words that are capitalised mid-sentence without being a player: the clubs, and what a lower third may say.
ALWAYS_CAPITALISED = {"Kestrel", "Ashvale", "FC", "Athletic", "VAR", "TV"}
DECISIVE_CLAIMS = re.compile(
    r"\b(made it|decided|decisive|won the game|the difference|lo hizo|decisiv)", re.I
)
COUNT_WORDS = {w.lower(): i for i, w in enumerate(NUMBER_WORDS)} | {
    w: i for i, w in enumerate(NUMBER_WORDS_ES)
}


def fact_check(copy: Copy, story: Story, everyone: set[str]) -> list[str]:
    """Everything in the copy the verified facts don't support. An empty list means it can go to air.

    Every lower third names the scorer in both languages and fits its graphic. Catches: players the facts
    don't name, a player's
    name misspelt or cut short, figures written as digits,
    a pass count that differs from the event feed, and a claim that one action decided the goal when the
    verdict was "shared".
    """
    allowed = {story.origin_player, story.scorer}
    if story.verdict == "decisive":
        allowed.add(story.credited_player)
    text = " ".join([copy.en_headline, copy.en_line, copy.es_headline, copy.es_line])
    problems = [
        f"names {name}" for name in sorted(everyone - allowed) if re.search(rf"\b{re.escape(name)}\b", text)
    ]
    problems += [f"uses the figure {d}" for d in re.findall(r"\d+(?:\.\d+)?", text)]
    problems += [
        f"{field} is {len(value)} characters; the graphic holds {LIMITS[field]}"
        for field, value in copy.model_dump().items()
        if len(value) > LIMITS[field]
    ]
    for word in re.findall(r"\b(\w+) (?:passes|pases)\b", text, re.I):
        if word.lower() in COUNT_WORDS and COUNT_WORDS[word.lower()] != story.passes:
            problems.append(f"says {word} passes, the feed has {story.passes}")
    known = everyone | allowed
    for word in set(re.findall(r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]{2,}\b", text)) - known:
        near = [n for n in known if SequenceMatcher(None, word.lower(), n.lower()).ratio() >= 0.8]
        if near:
            problems.append(f"misspells {near[0]} as {word}")
    for language, lines in (
        ("English", (copy.en_headline, copy.en_line)),
        ("Spanish", (copy.es_headline, copy.es_line)),
    ):
        if not any(re.search(rf"\b{re.escape(story.scorer)}\b", line) for line in lines):
            problems.append(f"the {language} copy doesn't name the scorer, {story.scorer}")
    apostrophes = "'\u2019"  # straight and typographic
    for line in copy.model_dump().values():
        for sentence in re.split(r"(?<=[.!?;:])\s+", line):
            for word in re.findall(rf"(?<=\s)[A-ZÁÉÍÓÚÑ][\wáéíóúñ{apostrophes}]+", sentence):
                name = re.sub(rf"[{apostrophes}]s$", "", word)
                if name not in known and name not in ALWAYS_CAPITALISED and not any(name in n for n in known):
                    problems.append(f"names {name}, who isn't in the facts")
    if story.verdict == "shared" and DECISIVE_CLAIMS.search(text):
        problems.append("claims one action decided it, but the credit is shared")
    return problems


class Check(Executor):
    @handler
    async def run(self, case: Case, ctx: WorkflowContext[Never, Case]) -> None:
        assert case.copy is not None and case.story is not None
        problems = fact_check(case.copy, case.story, set(case.request.players.values()))
        if problems:
            case.copy = await RuleWriter().write(case.story)
        summary = "passed" if not problems else "replaced the copy: " + ", ".join(problems)
        case.trace.append(Step("check", summary, 0.0))
        await ctx.yield_output(case)


def build(team: Team | None = None, model: ExpectedThreat | None = None):
    team = team or Team()
    steps = [
        Extract(id="extract"),
        Hypothesise(team),
        Experiment(model or ExpectedThreat()),
        Scrutinise(team),
        Verify(id="verify"),
        Write(team),
        Check(id="check"),
    ]
    return WorkflowBuilder(name=WORKFLOW_NAME, start_executor=steps[0]).add_chain(steps).build()


StepListener = Callable[[str, Step | None], Awaitable[None]]

WORKFLOW_NAME = "origins"

# Everything a checkpoint of this workflow carries between steps. Agent Framework restores only types it
# knows are safe, so each is registered once.
for _type in (Request, Step, Case, Credit, Verdict, Hypothesis, Hypotheses, Review, Copy, Story):
    register_checkpoint_type(_type)


async def investigate(
    request: Request,
    team: Team | None = None,
    on_step: StepListener | None = None,
    checkpoints: CheckpointStorage | None = None,
) -> Case:
    """Runs the investigation. `on_step(role, None)` fires when a step starts and `on_step(role, step)` when
    it finishes, so a studio can watch the agents work in real time.

    With `checkpoints`, Agent Framework saves the workflow after every superstep. If that storage already
    holds a checkpoint of this investigation (the server stopped part-way), the run resumes from it: the
    steps that finished are not run again, and the trace says so. A finished run leaves no checkpoints."""
    latest = await checkpoints.get_latest(workflow_name=WORKFLOW_NAME) if checkpoints else None
    if latest is not None:
        run = build(team).run(checkpoint_id=latest.checkpoint_id, checkpoint_storage=checkpoints, stream=True)
    else:
        run = build(team).run(request, checkpoint_storage=checkpoints, stream=True)
    case: Case | None = None
    async for event in run:
        if event.type == "output":
            case = event.data
        elif on_step and event.type == "executor_invoked":
            await on_step(event.executor_id, None)
        elif on_step and event.type == "executor_completed" and event.data:
            sent = event.data[0]
            await on_step(event.executor_id, sent.trace[-1] if isinstance(sent, Case) else None)
    assert case is not None, "the investigation finished without an answer"
    if latest is not None:
        note = f"resumed from a checkpoint after superstep {latest.iteration_count}; earlier steps not rerun"
        case.trace.insert(len(case.trace) - 1, Step("resume", note, 0.0))
    if checkpoints is not None and hasattr(checkpoints, "clear"):
        await checkpoints.clear()
    return case


def to_insight(case: Case) -> dict:
    """The investigation as a protocol Insight (insight.schema.json)."""
    assert case.verdict is not None and case.story is not None and case.hypotheses is not None
    request, top = case.request, case.verdict.top
    origin = case.chain[0]
    origin_credit = next(c for c in case.credits if c.event_id == origin["id"])
    origin_id = top.event_id if case.verdict.kind == "decisive" else origin["id"]
    return {
        "id": f"insight-{request.shot_id}",
        "matchId": request.match_id,
        "kind": "where_it_started",
        "pts": request.pts,
        "eventIds": [e["id"] for e in case.chain],
        "facts": [
            {"key": "origin_player", "value": case.story.origin_player, "eventIds": [origin["id"]]},
            {"key": "origin_where", "value": case.story.origin_where, "eventIds": [origin["id"]]},
            {
                "key": "passes",
                "value": case.story.passes,
                "eventIds": [e["id"] for e in case.chain if e["type"] == "pass"],
            },
            {"key": "scorer", "value": case.story.scorer, "eventIds": [case.chain[-1]["id"]]},
        ],
        "origin": {
            "eventId": origin_id,
            "playerId": (top.player_id if case.verdict.kind == "decisive" else origin.get("playerId")) or "",
            "verdict": case.verdict.kind,
            "valueAdded": top.value if case.verdict.kind == "decisive" else origin_credit.value,
            "interval": [origin_credit.low, origin_credit.high]
            if case.verdict.kind == "shared"
            else [top.low, top.high],
            "ruledOut": [h.event_id for h in case.hypotheses.items if h.event_id != origin_id],
        },
        "confidence": round(1 - (top.high - top.low), 3),
        "verified": True,
    }
