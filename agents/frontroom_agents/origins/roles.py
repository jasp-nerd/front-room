"""The three thinking roles in the origins investigation, each with a model-backed and a rule-based version.

- Hypothesis: proposes where a goal could really have started.
- Skeptic: argues with the evidence before anything is claimed.
- Writer: turns verified facts into a TV lower third, in English and Spanish.

The model versions run on Azure OpenAI through Agent Framework. The rule versions are what the tests use and
what a room falls back to, so an investigation always finishes even if the model is unreachable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Protocol

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from pydantic import BaseModel, Field

from .chain import MOVES, Credit


class Hypothesis(BaseModel):
    event_id: str
    reason: str = Field(description="One sentence, in football words, on why the goal could start here.")


class Hypotheses(BaseModel):
    items: list[Hypothesis] = Field(max_length=3)


class Review(BaseModel):
    objections: list[str] = Field(description="Where the evidence is weak. Short sentences.")
    recommendation: Literal["decisive", "shared"]
    reason: str


class Copy(BaseModel):
    """A lower third in English and Spanish. Lengths are checked by the fact check, not by the schema: a
    length limit in a structured-output schema makes a model stop mid-word instead of writing shorter."""

    en_headline: str
    en_line: str
    es_headline: str
    es_line: str


# The most characters each field can hold on the lower-third graphic.
LIMITS = {"en_headline": 34, "en_line": 70, "es_headline": 40, "es_line": 80}


@dataclass(frozen=True)
class Story:
    """The verified facts the writer may use, and nothing else."""

    verdict: Literal["decisive", "shared"]
    origin_player: str
    origin_action: str
    origin_where: str
    passes: int
    scorer: str
    credited_player: str
    credited_action: str


class Hypothesizer(Protocol):
    async def propose(self, chain: list[dict]) -> Hypotheses: ...


class Skeptic(Protocol):
    async def review(
        self, hypotheses: Hypotheses, credits: list[Credit], names: dict[str, str] | None = None
    ) -> Review: ...


class Writer(Protocol):
    async def write(self, story: Story, feedback: list[str] | None = None) -> Copy: ...


# Rule-based roles -----------------------------------------------------------------------------------------


class RuleHypothesizer:
    """The regain that started the move, plus the two actions that moved the ball furthest forward."""

    async def propose(self, chain: list[dict]) -> Hypotheses:
        start = chain[0]
        # Forward is the way the shot went: teams change ends at half-time.
        shot = chain[-1]
        towards = 1 if shot.get("end", shot["start"])["x"] >= shot["start"]["x"] else -1
        moves = [e for e in chain[1:] if "end" in e and e["type"] in MOVES]
        moves.sort(key=lambda e: towards * (e["end"]["x"] - e["start"]["x"]), reverse=True)
        picks = [start, *moves[:2]]
        return Hypotheses(
            items=[
                Hypothesis(
                    event_id=e["id"],
                    reason="won the ball back" if e is start else "moved it furthest forward",
                )
                for e in picks
            ]
        )


class RuleSkeptic:
    async def review(
        self, hypotheses: Hypotheses, credits: list[Credit], names: dict[str, str] | None = None
    ) -> Review:
        ranked = sorted(credits, key=lambda c: c.value, reverse=True)
        overlap = len(ranked) > 1 and ranked[0].low <= ranked[1].high
        objections = ["The top two intervals overlap."] if overlap else []
        recommendation: Literal["decisive", "shared"] = "shared" if overlap else "decisive"
        return Review(objections=objections, recommendation=recommendation, reason="Interval check only.")


NUMBER_WORDS = [
    "No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
    "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen",
    "Nineteen", "Twenty",
]  # fmt: skip
NUMBER_WORDS_ES = [
    "ningún", "un", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
    "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
    "diecinueve", "veinte",
]  # fmt: skip
# The origin actions that win the ball back. Anything else (a throw-in, a pass from the back) only starts it.
REGAINS = {"press", "tackle", "interception"}
ACTION_ES = {
    "press": "la presión",
    "tackle": "la entrada",
    "interception": "el robo",
    "pass": "el pase",
    "run": "la carrera",
}


def _fit(limit: int, *options: str) -> str:
    """The first phrasing that fits the graphic, or the last (shortest) one cut to fit."""
    return next((o for o in options if len(o) <= limit), options[-1][:limit])


class RuleWriter:
    """Fixed phrasings, longest first; each field takes the first one that fits its graphic."""

    async def write(self, story: Story, feedback: list[str] | None = None) -> Copy:
        # Beyond twenty the count is dropped ("Many passes later") rather than stated wrongly.
        passes = NUMBER_WORDS[story.passes] if story.passes < len(NUMBER_WORDS) else "Many"
        pases = NUMBER_WORDS_ES[story.passes] if story.passes < len(NUMBER_WORDS_ES) else "muchos"
        if story.verdict == "decisive":
            player, action = story.credited_player, story.credited_action
            action_es = ACTION_ES.get(action, "la jugada")
            # The decisive action takes the headline; the line still credits whoever won the ball back.
            origin, origin_es = story.origin_player, ACTION_ES.get(story.origin_action, "la jugada")
            return Copy(
                en_headline=_fit(34, f"{player}'s {action} made it", f"{player} made it"),
                en_line=_fit(
                    70,
                    f"It started with {origin}'s {story.origin_action}. {story.scorer} scored.",
                    f"{passes} passes after the ball was won, {story.scorer} scored.",
                    f"{story.scorer} scored.",
                ),
                es_headline=_fit(40, f"Lo hizo {action_es} de {player}", f"Lo hizo {player}"),
                es_line=_fit(
                    80,
                    f"Empezó con {origin_es} de {origin}. Marcó {story.scorer}.",
                    f"{story.scorer} marcó tras {pases} pases.",
                    f"Marcó {story.scorer}.",
                ),
            )
        player, action = story.origin_player, story.origin_action
        action_es = ACTION_ES.get(action, "la jugada")
        return Copy(
            en_headline=_fit(
                34,
                f"It started with {player}'s {action}",
                f"Started with {player}'s {action}",
                f"It started with {player}",
            ),
            en_line=_fit(
                70,
                *(
                    [
                        f"{player} won it back {story.origin_where}. "
                        f"{passes} passes later, {story.scorer} scored.",
                        f"{player} won it back. {passes} passes later, {story.scorer} scored.",
                    ]
                    if action in REGAINS
                    else [f"It began {story.origin_where}. {passes} passes later, {story.scorer} scored."]
                ),
                f"{passes} passes later, {story.scorer} scored.",
            ),
            es_headline=_fit(40, f"Empezó con {action_es} de {player}", f"Empezó con {player}"),
            es_line=_fit(80, f"{story.scorer} marcó {pases} pases después.", f"Marcó {story.scorer}."),
        )


# Model-backed roles ---------------------------------------------------------------------------------------

HYPOTHESIS_INSTRUCTIONS = """\
You are a football analyst looking at the possession that led to a goal. Each action has an id, a player,
a type and positions in metres with the team attacking towards x = 105. Propose up to three actions where the
goal could really have started, each with one short football reason. Include the action that won the ball
back. Use only the ids you are given.
"""

SKEPTIC_INSTRUCTIONS = """\
You are the skeptic on an analytics team. You get the hypotheses and, for each action, its measured value
against what a typical player would have done from the same spot, with a 90% interval. Point out where the
evidence is weak: overlapping intervals, values below 0.05, and what on-ball data cannot see, such as runs
and screens. Refer to actions by their "action" name, never by id. Recommend "decisive" only if one action
clearly stands out. Never invent numbers.
"""

WRITER_INSTRUCTIONS = """\
You write lower thirds for a live football broadcast, in natural spoken English and Spanish as a good
commentator says it: possessives and articles included ("Mensah's press", "la presión de Mensah"), never
clipped headline-ese ("Mensah press"). Use only the facts you are given: no other names, no
numbers that are not in them, no adjectives about quality. Write numbers as words ("three", not "3").
Name the scorer, spelt exactly as given, in both languages. Credit, never blame. Sentence case, no full stop
on headlines. English headline at most 34 characters and line at most 70. Then Spanish (neutral Latin
American, never "vosotros"): headline at most 40 characters, line at most 80.
If the verdict is "shared", the headline is about where the move started and must not claim one action
decided the goal. If it is "decisive", the headline credits that action and the line still says where the
move started, so the player who won the ball back gets their credit too. Say someone "won it back" only if
the origin action is a press, a tackle or an interception; a throw-in, free kick or pass only started the
move. The headline is a full statement
with a verb ("Okafor's run made it", never just "Okafor's run"), and the line ends with the goal: who scored.
"""


class _ModelRole:
    def __init__(self, client: OpenAIChatClient, name: str, instructions: str):
        self.agent = Agent(client=client, name=name, instructions=instructions)

    async def ask(self, payload: object, shape: type[BaseModel]):
        response = await self.agent.run(json.dumps(payload, default=str), options={"response_format": shape})
        if response.value is None:
            # A refusal or an empty reply parses to nothing; failing hands the step to its rule-based role.
            raise ValueError(f"{self.agent.name} returned no {shape.__name__}")
        return response.value


class ModelHypothesizer(_ModelRole):
    def __init__(self, client: OpenAIChatClient):
        super().__init__(client, "hypothesis", HYPOTHESIS_INSTRUCTIONS)

    async def propose(self, chain: list[dict]) -> Hypotheses:
        actions = [
            {k: e.get(k) for k in ("id", "playerName", "type", "result", "start", "end")} for e in chain
        ]
        return await self.ask({"possession": actions}, Hypotheses)


class ModelSkeptic(_ModelRole):
    def __init__(self, client: OpenAIChatClient):
        super().__init__(client, "skeptic", SKEPTIC_INSTRUCTIONS)

    async def review(
        self, hypotheses: Hypotheses, credits: list[Credit], names: dict[str, str] | None = None
    ) -> Review:
        # Actions are named the way the studio reads them ("Mensah's press"), so the review is too.
        name = (names or {}).get
        return await self.ask(
            {
                "hypotheses": [
                    {**h, "action": name(h["event_id"], h["event_id"])}
                    for h in hypotheses.model_dump()["items"]
                ],
                "measured": [{**vars(c), "action": name(c.event_id, c.event_id)} for c in credits],
            },
            Review,
        )


class ModelWriter(_ModelRole):
    def __init__(self, client: OpenAIChatClient):
        super().__init__(client, "writer", WRITER_INSTRUCTIONS)

    async def write(self, story: Story, feedback: list[str] | None = None) -> Copy:
        facts = vars(story)
        if story.verdict == "shared":
            # With shared credit nobody is credited, so the writer never sees a name it could wrongly credit.
            facts = {k: v for k, v in facts.items() if not k.startswith("credited_")}
        request = {"facts": facts, "character_limits": LIMITS}
        if feedback:
            request["fix_these_problems_from_your_last_draft"] = feedback
        return await self.ask(request, Copy)
