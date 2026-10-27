"""Can anything untrue reach the TV? Two evaluations of the words the origins workflow puts on air.

1. Planted errors (offline, deterministic). For a few hundred random goals we write correct copy, then plant
   one error of each kind a writer could make: naming a player the facts don't support, inventing a player,
   misspelling a name, writing a figure as digits, getting the pass count wrong, and claiming one action
   decided a goal whose credit is shared.
   We report how many planted errors the fact check catches, and how much correct copy it wrongly rejects.

2. The live writer (FRONTROOM_LIVE=1). The model writer drafts copy for random goals and, as in the
   workflow, revises once if the fact check objects. We report how often it needed that revision, how often
   the final draft passes, and how often a separate model judge finds a claim the facts don't support.

    python -m frontroom_agents.evals.copy            # planted errors only
    FRONTROOM_LIVE=1 python -m frontroom_agents.evals.copy --live 40
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel

from ..origins.roles import NUMBER_WORDS, Copy, RuleWriter, Story
from ..origins.workflow import fact_check

ROSTER = [
    "Mensah",
    "Ito",
    "Vidal",
    "Okafor",
    "Lund",
    "Rios",
    "Adeyemi",
    "Kovac",
    "Silva",
    "Brandt",
    "Haddad",
    "Moreau",
]
ACTIONS = ["press", "tackle", "interception"]
WHERES = ["deep in their own half", "on halfway", "in the final third"]
RESULTS = Path(__file__).with_name("copy-results.json")


def random_story(rng: random.Random) -> Story:
    origin, scorer, credited = rng.sample(ROSTER, 3)
    return Story(
        verdict=rng.choice(["decisive", "shared"]),
        origin_player=origin,
        origin_action=rng.choice(ACTIONS),
        origin_where=rng.choice(WHERES),
        passes=rng.randint(1, 6),
        scorer=scorer,
        credited_player=credited,
        credited_action="pass",
    )


def plant(copy: Copy, story: Story, kind: str, rng: random.Random) -> Copy:
    """One error of the given kind, put where a writer would plausibly make it."""
    if kind == "unsupported player":
        stranger = rng.choice(
            [n for n in ROSTER if n not in {story.origin_player, story.scorer, story.credited_player}]
        )
        return replace_copy(copy, en_line=f"{stranger} started it. {story.scorer} scored.")
    if kind == "invented player":
        return replace_copy(copy, en_line=f"Then Smith found {story.scorer}.")
    if kind == "misspelt name":
        return replace_copy(copy, es_line=f"Marcó {story.scorer[:-1]}.")
    if kind == "digits":
        return replace_copy(copy, en_line=f"{story.passes} passes later, {story.scorer} scored.")
    if kind == "wrong pass count":
        wrong = NUMBER_WORDS[(story.passes % 6) + 1 if story.passes < 6 else 2]
        return replace_copy(copy, en_line=f"{wrong} passes later, {story.scorer} scored.")
    if kind == "decisive claim":
        return replace_copy(copy, en_headline=f"{story.origin_player}'s {story.origin_action} made it")
    raise ValueError(kind)


def replace_copy(copy: Copy, **fields: str) -> Copy:
    return Copy.model_construct(**{**copy.model_dump(), **fields})


async def planted_errors(goals: int = 300, seed: int = 11) -> dict:
    rng = random.Random(seed)
    writer = RuleWriter()
    kinds = [
        "unsupported player",
        "invented player",
        "misspelt name",
        "digits",
        "wrong pass count",
        "decisive claim",
    ]
    caught = {k: 0 for k in kinds}
    planted = {k: 0 for k in kinds}
    false_rejects = 0
    for _ in range(goals):
        story = random_story(rng)
        good = await writer.write(story)
        if fact_check(good, story, set(ROSTER)):
            false_rejects += 1
        for kind in kinds:
            if kind == "decisive claim" and story.verdict == "decisive":
                continue
            target = story if kind != "wrong pass count" else replace(story, passes=max(story.passes, 1))
            bad = plant(good, target, kind, rng)
            planted[kind] += 1
            caught[kind] += bool(fact_check(bad, target, set(ROSTER)))
    return {
        "goals": goals,
        "caught": {k: f"{caught[k]}/{planted[k]}" for k in kinds},
        "catch_rate": round(sum(caught.values()) / sum(planted.values()), 3),
        "false_rejects": f"{false_rejects}/{goals}",
    }


class Grade(BaseModel):
    unsupported_claims: list[str]
    grounded: bool


JUDGE_INSTRUCTIONS = """\
You check football graphics for accuracy. You get the verified facts and a draft lower third in English and
Spanish. List every claim in the draft that the facts do not support (names, counts, who decided the goal,
anything about quality or emotion). grounded is true only if that list is empty.
"""


async def live_writer(goals: int, seed: int = 12) -> dict:
    from agent_framework import Agent

    from .. import llm
    from ..origins.roles import ModelWriter

    rng = random.Random(seed)
    passed_check = grounded = revised = 0
    examples = []
    async with llm.credential() as cred:
        client = llm.chat_client(cred)
        writer, judge = (
            ModelWriter(client),
            Agent(client=client, name="judge", instructions=JUDGE_INSTRUCTIONS),
        )
        for _ in range(goals):
            story = random_story(rng)
            draft = await writer.write(story)
            first_problems = fact_check(draft, story, set(ROSTER))
            if first_problems:
                revised += 1
                draft = await writer.write(story, feedback=first_problems)
            problems = fact_check(draft, story, set(ROSTER))
            passed_check += not problems
            verdict = await judge.run(
                json.dumps({"facts": vars(story), "draft": draft.model_dump()}),
                options={"response_format": Grade},
            )
            grounded += verdict.value.grounded
            # Keep every draft either check flagged, plus a few clean ones for reference.
            if not verdict.value.grounded or problems or len(examples) < 3:
                examples.append(
                    {"draft": draft.model_dump(), "fact_check": problems, "judge": verdict.value.model_dump()}
                )
    return {
        "goals": goals,
        "revised_once": f"{revised}/{goals}",
        "passed_fact_check": f"{passed_check}/{goals}",
        "judged_grounded": f"{grounded}/{goals}",
        "examples": examples,
    }


async def main(live: int) -> None:
    results = {"planted_errors": await planted_errors()}
    if live:
        results["live_writer"] = await live_writer(live)
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", type=int, default=0, help="also run the model writer on this many goals")
    asyncio.run(main(parser.parse_args().live))
