"""Foundry Evaluations: Front Room's agents judged with azure-ai-evaluation, by the Foundry project's gpt-5.4
(FRONTROOM_JUDGE_MODEL), a different model from the gpt-5.6-luna agents it grades.

Every row is one goal from the engine's demo match played into one room on the real room-server code, with
every agent on the Foundry project's models: the fans' profilers and personal agents on gpt-5.4-mini, and the
goal investigation (hypothesis, skeptic, writer) on gpt-5.6-luna. Seven goals in three rooms: 21 rows.

Each row is scored by:
- Foundry's built-in AI-assisted evaluators: Groundedness (the TV's words against the facts the writer was
  given), Relevance, Coherence and Fluency, all judged by gpt-5.4 (a reasoning model);
- Front Room's code evaluators (evals/foundry_evaluators.py): fact check, fairness, privacy and spoiler.

    uv run python -m frontroom_agents.evals.foundry [--rooms both-clubs,home-only,mixed-pair] [--reuse]

Results: evals/foundry-results.json (aggregate and per row) and evals/foundry-results.md (a summary).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean

from azure.ai.evaluation import (
    CoherenceEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
    RelevanceEvaluator,
    evaluate,
)

from .. import telemetry
from ..foundry.settings import judge_config, settings
from ..server.demo_source import DEMO_FANS, demo_source
from .foundry_evaluators import FactCheckEvaluator, FairnessEvaluator, PrivacyEvaluator, SpoilerEvaluator
from .foundry_rooms import Agents, play

HERE = Path(__file__).parent
DATA = HERE / "foundry-data.jsonl"
RESULTS = HERE / "foundry-results.json"
SUMMARY = HERE / "foundry-results.md"

ROOMS: dict[str, dict[str, str]] = {
    # The demo family: both clubs on the sofa, so the TV must stay neutral.
    "both-clubs": DEMO_FANS,
    # Three Kestrel fans: a one-club overlay is allowed to win.
    "home-only": {
        "rob": DEMO_FANS["rob"],
        "sam": DEMO_FANS["sam"],
        "maya": "Kestrel season ticket holder. Tactics please, how did we press?",
    },
    # Two fans of different clubs who say little.
    "mixed-pair": {
        "ines": "Ashvale till I die. Keep it short.",
        "tom": "Kestrel. I mostly want to see the goals again.",
    },
}

BUILT_IN = ("groundedness", "relevance", "coherence", "fluency")
OURS = ("fact_check", "fairness", "privacy", "spoiler")


async def collect(rooms: list[str]) -> list[dict]:
    source = demo_source()
    agents = Agents.on_foundry()
    rows = []
    for room in rooms:
        for goal in source.goals:
            rows.append(await play(f"eval-{room}", ROOMS[room], goal, agents, source))
            print(f"{room} {goal.shot_id}: {rows[-1]['response'].splitlines()[0]}")
    return rows


def _columns(*names: str) -> dict[str, str]:
    return {n: f"${{data.{n}}}" for n in names}


def run_evaluation() -> dict:
    judge = judge_config()
    # gpt-5.4 is a reasoning model: the evaluators must not send temperature or max_tokens.
    evaluators = {
        "groundedness": GroundednessEvaluator(judge, is_reasoning_model=True),
        "relevance": RelevanceEvaluator(judge, is_reasoning_model=True),
        "coherence": CoherenceEvaluator(judge, is_reasoning_model=True),
        "fluency": FluencyEvaluator(judge, is_reasoning_model=True),
        "fact_check": FactCheckEvaluator(),
        "fairness": FairnessEvaluator(),
        "privacy": PrivacyEvaluator(),
        "spoiler": SpoilerEvaluator(),
    }
    config = {
        "groundedness": {"column_mapping": _columns("query", "context", "response")},
        "relevance": {"column_mapping": _columns("query", "response")},
        "coherence": {"column_mapping": _columns("query", "response")},
        "fluency": {"column_mapping": _columns("response")},
        "fact_check": {"column_mapping": _columns("copy", "story", "roster")},
        "fairness": {"column_mapping": _columns("both_clubs", "winner", "winner_partisan")},
        "privacy": {"column_mapping": _columns("tv_text", "fans", "roster", "context")},
        "spoiler": {"column_mapping": _columns("sends")},
    }
    return evaluate(
        data=str(DATA),
        evaluators=evaluators,
        evaluator_config=config,
        evaluation_name="front-room-agents",
    )


def summarise(result: dict, rows: list[dict]) -> dict:
    per_row = result["rows"]

    def scores(name: str) -> list[float]:
        return [r[f"outputs.{name}.{name}"] for r in per_row if r.get(f"outputs.{name}.{name}") is not None]

    def failures(name: str) -> list[str]:
        return [
            f"{r['inputs.room']} {r['inputs.goal']}: {r.get(f'outputs.{name}.{name}_reason', '')}"
            for r in per_row
            if r.get(f"outputs.{name}.{name}") == 0.0
        ]

    built_in = {
        n: {
            "mean_1_to_5": round(mean(scores(n)), 2),
            "passing": f"{sum(s >= 3 for s in scores(n))}/{len(scores(n))}",
        }
        for n in BUILT_IN
        if scores(n)
    }
    ours = {n: {"held": f"{int(sum(scores(n)))}/{len(scores(n))}", "failures": failures(n)} for n in OURS}
    fallbacks = sum("fallback" in step for row in rows for step in row["trace"])
    replaced = sum(step.startswith("check: replaced") for row in rows for step in row["trace"])
    return {
        "rows": len(rows),
        "judge": f"Foundry {settings().judge} (azure-ai-evaluation, reasoning-model mode)",
        "agents": f"Foundry {settings().model} (investigation) and {settings().model_fast} (fans' agents)",
        "built_in": built_in,
        "front_room_rules": ours,
        "model_steps_that_fell_back_to_rules": fallbacks,
        "writer_copy_replaced_by_the_fact_check": replaced,
        "studio_url": result.get("studio_url"),
    }


def write_markdown(summary: dict) -> None:
    lines = [
        "# Foundry evaluation of Front Room's agents",
        "",
        f"{summary['rows']} rows: every goal of the demo match, played into three rooms on the real "
        "room-server code.",
        f"Agents: {summary['agents']}. Judge: {summary['judge']}.",
        "",
        "| Built-in evaluator | Mean (1 to 5) | Rows scoring 3 or more |",
        "|---|---|---|",
        *(f"| {n} | {v['mean_1_to_5']} | {v['passing']} |" for n, v in summary["built_in"].items()),
        "",
        "| Front Room rule | Held |",
        "|---|---|",
        *(f"| {n} | {v['held']} |" for n, v in summary["front_room_rules"].items()),
        "",
        f"Model steps that fell back to rules: {summary['model_steps_that_fell_back_to_rules']}. "
        "Writer copy the fact "
        f"check replaced with the rule-based writer's: {summary['writer_copy_replaced_by_the_fact_check']}.",
        "",
    ]
    for name, v in summary["front_room_rules"].items():
        for failure in v["failures"]:
            lines.append(f"- {name} failed: {failure}")
    SUMMARY.write_text("\n".join(lines).rstrip() + "\n")


async def main(rooms: list[str], reuse: bool) -> None:
    telemetry.setup()
    if reuse and DATA.exists():
        rows = [json.loads(line) for line in DATA.read_text().splitlines() if line]
    else:
        rows = await collect(rooms)
        DATA.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    result = run_evaluation()
    summary = summarise(result, rows)
    RESULTS.write_text(
        json.dumps({"summary": summary, "rows": result["rows"]}, indent=2, ensure_ascii=False) + "\n"
    )
    write_markdown(summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    telemetry.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rooms", default=",".join(ROOMS), help="comma-separated rooms to play")
    parser.add_argument("--reuse", action="store_true", help="score the rows already in foundry-data.jsonl")
    args = parser.parse_args()
    asyncio.run(main(args.rooms.split(","), args.reuse))
