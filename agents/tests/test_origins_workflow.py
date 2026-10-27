import asyncio
import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource
from tests.test_origins_chain import MATCH

from frontroom_agents.origins.roles import Copy, Story
from frontroom_agents.origins.workflow import Request, Team, fact_check, investigate, to_insight

PLAYERS = {"home-2": "Mensah", "home-3": "Ito", "home-4": "Vidal", "home-5": "Diallo", "home-6": "Okafor"}
REQUEST = Request("demo", "ev-6", 3_792_000, MATCH, PLAYERS | {"away-1": "Lund"}, attacking_right=True)
SCHEMAS = Path(__file__).parents[2] / "packages" / "protocol" / "schema"


def test_the_investigation_runs_every_step_and_says_where_it_started():
    case = asyncio.run(investigate(REQUEST))
    assert [s.role for s in case.trace] == [
        "extract",
        "hypothesis",
        "experiment",
        "skeptic",
        "verify",
        "writer",
        "check",
    ]
    assert case.verdict.kind == "shared"
    assert case.copy.en_headline == "It started with Mensah's tackle"
    assert "Okafor" in case.copy.en_line


def test_a_failing_model_falls_back_to_rules_and_says_so():
    class Down:
        async def propose(self, chain):
            raise TimeoutError

        async def review(self, hypotheses, credits, names=None):
            raise TimeoutError

        async def write(self, story, feedback=None):
            raise TimeoutError

    case = asyncio.run(investigate(REQUEST, Team(Down(), Down(), Down())))
    notes = {s.role: s.summary for s in case.trace}
    assert "model unavailable" in notes["hypothesis"] and "model unavailable" in notes["writer"]
    assert case.copy is not None


def test_copy_naming_a_player_the_facts_dont_support_is_rejected():
    story = Story("shared", "Mensah", "tackle", "on halfway", 3, "Okafor", "Diallo", "pass")
    invented = Copy(
        en_headline="Lund gave it away",
        en_line="Okafor scored 2 minutes later.",
        es_headline="Lund la perdió",
        es_line="Okafor marcó.",
    )
    problems = fact_check(invented, story, set(REQUEST.players.values()))
    assert "names Lund" in problems and "uses the figure 2" in problems


def test_the_insight_matches_the_protocol_schema():
    insight = to_insight(asyncio.run(investigate(REQUEST)))
    schemas = {p.name: json.loads(p.read_text()) for p in SCHEMAS.glob("*.schema.json")}
    registry = Registry().with_resources((name, Resource.from_contents(s)) for name, s in schemas.items())
    jsonschema.Draft202012Validator(schemas["insight.schema.json"], registry=registry).validate(insight)


@pytest.mark.live
def test_live_team_produces_checked_copy():
    from frontroom_agents import llm
    from frontroom_agents.origins.roles import ModelHypothesizer, ModelSkeptic, ModelWriter

    if not llm.live():
        pytest.skip("set FRONTROOM_LIVE=1 to call Azure OpenAI")

    async def go():
        async with llm.credential() as cred:
            client = llm.chat_client(cred)
            return await investigate(
                REQUEST, Team(ModelHypothesizer(client), ModelSkeptic(client), ModelWriter(client))
            )

    case = asyncio.run(go())
    for step in case.trace:
        print(f"{step.role:>10} {step.ms:>7} ms  {step.summary}")
    print(case.copy)
    assert all("model unavailable" not in s.summary for s in case.trace)


def test_a_model_that_answers_with_nothing_hands_over_to_the_rules():
    from frontroom_agents.origins.roles import ModelWriter

    class Silent:
        name = "writer"

        async def run(self, *args, **kwargs):
            class Empty:
                value = None

            return Empty()

    writer = ModelWriter.__new__(ModelWriter)
    writer.agent = Silent()
    case = asyncio.run(investigate(REQUEST, Team(writer=writer)))
    assert "model unavailable" in next(s.summary for s in case.trace if s.role == "writer")
    assert case.copy.en_headline


def test_the_origin_is_never_also_ruled_out():
    insight = to_insight(asyncio.run(investigate(REQUEST)))
    assert insight["origin"]["eventId"] not in insight["origin"]["ruledOut"]


def test_an_invented_player_is_caught():
    story = Story("shared", "Mensah", "tackle", "on halfway", 3, "Okafor", "Diallo", "pass")
    invented = Copy(
        en_headline="It started with Mensah's tackle",
        en_line="Then Smith found Okafor.",
        es_headline="Empezó con Mensah",
        es_line="Marcó Okafor.",
    )
    assert "names Smith, who isn't in the facts" in fact_check(invented, story, set(PLAYERS.values()))
