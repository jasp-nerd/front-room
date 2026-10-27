import asyncio

import pytest

from frontroom_agents.personal.agent import ModelScorer, Offer, PersonalAgent, RuleScorer, Valuation
from frontroom_agents.personal.profile import FanProfile
from frontroom_agents.room.demo import KEEPERS_VIEW, PRESSING_MAP, WHERE_IT_STARTED, front_room
from frontroom_agents.room.director import Constraint
from frontroom_agents.room.session import run_round

OFFERS = [
    Offer(WHERE_IT_STARTED, "Where it started", "The press that began the goal", "story"),
    Offer(PRESSING_MAP, "Kestrel's pressing map", "How Kestrel pressed", "tactics", favours="kestrel"),
    Offer(
        KEEPERS_VIEW,
        "How Ashvale's keeper saw it",
        "The shot from the goal line",
        "keeper",
        favours="ashvale",
    ),
]

PROFILES = {
    "rob": FanProfile(club="kestrel", depth="analyst", language="en"),
    "ana": FanProfile(club="ashvale", depth="casual", language="es", needs=["captions"]),
    "leo": FanProfile(club="kestrel", depth="kid", language="en"),
    "sam": FanProfile(club="kestrel", depth="audio", language="en", needs=["described-audio"]),
}


def room(scorers=None):
    scorers = scorers or {}
    return [PersonalAgent(fan, profile, scorers.get(fan, RuleScorer())) for fan, profile in PROFILES.items()]


class Slow:
    async def value(self, profile, offers):
        await asyncio.sleep(5)
        return {}


class Broken:
    async def value(self, profile, offers):
        raise RuntimeError("model unreachable")


def test_a_room_of_rule_agents_puts_the_neutral_story_on_the_tv():
    result = asyncio.run(run_round(room(), OFFERS, front_room()))
    assert result.decision.winner == WHERE_IT_STARTED.id
    assert result.dropped == []
    struck = {c.candidate_id: c.struck_by for c in result.decision.candidates}
    assert struck[PRESSING_MAP.id] is Constraint.NEUTRAL_FRAMING


def test_late_and_failing_agents_are_dropped_and_the_room_still_decides_on_time():
    agents = room({"rob": Slow(), "ana": Broken()})
    result = asyncio.run(run_round(agents, OFFERS, front_room(), deadline_s=0.05))
    assert sorted(result.dropped) == ["ana", "rob"]
    assert {b.agent_id for b in result.bids} == {"leo", "sam"}
    assert result.decision.winner is not None


def test_a_fan_values_their_rivals_overlay_less_than_their_own_clubs():
    values = asyncio.run(RuleScorer().value(PROFILES["ana"], OFFERS))
    assert values[KEEPERS_VIEW.id].utility > values[PRESSING_MAP.id].utility


def test_the_model_scorer_falls_back_to_rules_when_the_call_fails():
    class Failing:
        async def run(self, *args, **kwargs):
            raise ConnectionError

    scorer = ModelScorer.__new__(ModelScorer)
    scorer._agent = Failing()
    scorer._fallback = RuleScorer()
    values = asyncio.run(scorer.value(PROFILES["rob"], OFFERS))
    assert values == asyncio.run(RuleScorer().value(PROFILES["rob"], OFFERS))


def test_reasons_stay_with_the_agent_and_bids_carry_only_numbers():
    class Explaining:
        async def value(self, profile, offers):
            return {o.candidate.id: Valuation(0.5, "Rob loves a press") for o in offers}

    agent = PersonalAgent("rob", PROFILES["rob"], Explaining())
    bids = asyncio.run(agent.bid(OFFERS))
    assert all(set(vars(b)) == {"agent_id", "candidate_id", "utility"} for b in bids)
    assert agent.reasons[PRESSING_MAP.id] == "Rob loves a press"


@pytest.mark.live
def test_live_model_scores_every_offer_for_a_real_profile():
    from frontroom_agents import llm

    if not llm.live():
        pytest.skip("set FRONTROOM_LIVE=1 to call Azure OpenAI")

    async def go():
        async with llm.credential() as cred:
            scorer = ModelScorer(llm.chat_client(cred))
            return await scorer.value(PROFILES["rob"], OFFERS)

    values = asyncio.run(go())
    assert set(values) == {o.candidate.id for o in OFFERS}
    assert values[PRESSING_MAP.id].utility > values[KEEPERS_VIEW.id].utility
