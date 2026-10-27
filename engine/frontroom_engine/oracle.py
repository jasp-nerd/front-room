"""The origins oracle: how much each action in a goal's possession really changed the chance.

For every on-ball decision the scoring side made in the possession that led to the goal,

    tau = E[Y | the action taken] - sum_i p_i E[Y | option i]

where the options and their probabilities p_i are the ones the decision model offered that
player at that moment (the chosen option included), and Y is the net physical xG over the next
15 seconds. That is the action's advantage over what a typical player with the same view of
the pitch would have done. Each E[.] is estimated from the same K resampled futures for every
option (common random numbers), so tau has K paired samples; its interval is a percentile
bootstrap over them. A regain (the tackle or interception that started the possession) is not
a choice in this simulator, so its tau compares winning the ball with the same player kept off
it. The action with the largest tau is "decisive" when tau >= 0.05 and its lower bound clears
the upper bound of every other action; otherwise the goal is "shared".
"""

import json
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from frontroom_engine.calibration.scorecard import fixture
from frontroom_engine.counterfactual import HORIZON_TICKS, Checkpoint, replay_checkpoints, run_alternative
from frontroom_engine.extract.events import Feed, extract_events
from frontroom_engine.io import write_match
from frontroom_engine.league import DEFAULT_LEAGUE_SEED, build_league
from frontroom_engine.sim.match import MatchResult, simulate_match
from frontroom_engine.sim.recorder import Recording
from frontroom_engine.sim.records import Action, Decision

SAMPLES = 8
MAX_OPTIONS = 6
MIN_PROBABILITY = 0.01
DECISIVE_TAU = 0.05
BOOTSTRAP = 1000
REGAIN_WINDOW_TICKS = 30
SALT_BASE = 1_000_000_000
DECIDED_KINDS = {
    "pass",
    "cross",
    "throw_in",
    "corner",
    "free_kick",
    "goal_kick",
    "shot",
    "penalty",
    "take_on",
}
CARRY_CHOICES = {"carry", "take_on", "hold"}
REGAIN_KINDS = {"tackle", "interception"}


@dataclass(frozen=True)
class Intervention:
    action: Action
    tick: int
    decision: Decision | None
    """None for a regain, which is removed rather than swapped for an alternative."""


def _decision_for(
    action: Action, decisions: list[Decision], by_action: dict[int, Decision]
) -> Decision | None:
    if action.kind in DECIDED_KINDS:
        return by_action.get(action.id)
    end = action.end_tick if action.end_tick is not None else action.tick
    return next(
        (
            d
            for d in decisions
            if d.player_id == action.player_id
            and action.tick <= d.tick <= end
            and d.options[d.chosen].kind in CARRY_CHOICES
        ),
        None,
    )


def _regain(actions: list[Action], team: int, start_tick: int) -> Action | None:
    """The tackle or interception by `team` that won the ball just before its possession began."""
    candidates = [
        a
        for a in actions
        if a.team == team
        and a.kind in REGAIN_KINDS
        and a.result == "success"
        and start_tick - REGAIN_WINDOW_TICKS <= a.tick <= start_tick
    ]
    return max(candidates, key=lambda a: (a.tick, a.id), default=None)


def scoring_move(result: MatchResult, goal: Action) -> list[Action]:
    """The regain (if any) and every on-ball action of the scoring side in the goal's possession."""
    actions = sorted(result.state.actions, key=lambda a: (a.tick, a.id))
    move = [
        a
        for a in actions
        if a.possession == goal.possession
        and a.team == goal.team
        and a.tick <= goal.tick
        and (a.kind in DECIDED_KINDS or a.kind == "dribble")
    ]
    regain = _regain(actions, goal.team, move[0].tick) if move else None
    return ([regain] if regain else []) + move


def _plan(result: MatchResult, move: list[Action]) -> tuple[list[Intervention], list[tuple[Action, str]]]:
    """Where to intervene for each action, and which actions have no decision to intervene on."""
    decisions = result.state.decisions
    by_action = {d.action_id: d for d in decisions}
    planned: list[Intervention] = []
    skipped: list[tuple[Action, str]] = []
    for action in move:
        if action.kind in REGAIN_KINDS:
            planned.append(Intervention(action, action.tick, None))
            continue
        decision = _decision_for(action, decisions, by_action)
        if decision is None:
            skipped.append((action, "no decision behind it (a first-time header or volley)"))
        else:
            planned.append(Intervention(action, decision.tick, decision))
    return planned, skipped


def _options(decision: Decision) -> tuple[list[int], np.ndarray]:
    probabilities = np.array(decision.probabilities)
    ranked = [int(i) for i in np.argsort(-probabilities) if probabilities[i] >= MIN_PROBABILITY][:MAX_OPTIONS]
    considered = sorted(set(ranked) | {decision.chosen})
    weights = probabilities[considered]
    return considered, weights / weights.sum()


def _bootstrap(samples: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = rng.choice(samples, size=(BOOTSTRAP, len(samples)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def tau_samples(
    result: MatchResult,
    checkpoint: Checkpoint,
    slot: int,
    decision: Decision | None,
    samples: int,
    recording: Recording,
) -> np.ndarray:
    """Paired per-future estimates of tau for one action."""
    setup = result.setup
    salts = [SALT_BASE + k for k in range(samples)]
    if decision is None:
        kept = [run_alternative(setup, checkpoint, slot, salt=s, recording=recording) for s in salts]
        removed = [
            run_alternative(setup, checkpoint, slot, withhold=True, salt=s, recording=recording)
            for s in salts
        ]
        return np.array(kept) - np.array(removed)
    considered, weights = _options(decision)
    values = np.array(
        [
            [run_alternative(setup, checkpoint, slot, option, salt=s, recording=recording) for s in salts]
            for option in considered
        ],
        dtype=float,
    )
    valid = ~np.isnan(values).any(axis=0)
    values = values[:, valid]
    return values[considered.index(decision.chosen)] - weights @ values


def verdict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Decisive if the top tau is at least 0.05 and its interval clears every other action's."""
    if not rows:
        return {"label": "shared", "decisiveEventId": None}
    ranked = sorted(rows, key=lambda r: r["tau"], reverse=True)
    top = ranked[0]
    runner_up_high = max((r["high"] for r in ranked[1:]), default=0.0)
    decisive = top["tau"] >= DECISIVE_TAU and top["low"] > runner_up_high
    return {
        "label": "decisive" if decisive else "shared",
        "decisiveEventId": top["eventId"] if decisive else None,
    }


def _row(action: Action, decision: Decision | None, taus: np.ndarray, feed: Feed) -> dict[str, Any]:
    low, high = _bootstrap(taus, action.id) if len(taus) > 1 else (float(taus[0]), float(taus[0]))
    return {
        "eventId": feed.event_ids.get(action.id),
        "type": action.kind,
        "playerId": action.player_id,
        "intervention": "alternatives" if decision else "remove_regain",
        "options": len(_options(decision)[0]) if decision else 2,
        "samples": len(taus),
        "tau": round(float(np.mean(taus)), 4),
        "low": round(low, 4),
        "high": round(high, 4),
    }


def _shot_for(actions: list[Action], goal: Action) -> Action | None:
    shots = [
        a
        for a in actions
        if a.kind in ("shot", "penalty")
        and a.result == "success"
        and a.player_id == goal.player_id
        and a.tick <= goal.tick
    ]
    return max(shots, key=lambda a: a.tick, default=None)


def attribute_goals(result: MatchResult, feed: Feed, samples: int = SAMPLES) -> list[dict[str, Any]]:
    """Oracle records for every goal in the match that stood (own goals and VAR-disallowed goals excluded)."""
    actions = result.state.actions
    overturned = {a.detail.get("goalAction") for a in actions if a.kind == "var_decision"}
    goals = [a for a in actions if a.kind == "goal" and a.result == "success" and a.id not in overturned]
    plans = [(goal, *_plan(result, scoring_move(result, goal))) for goal in goals]
    checkpoints = replay_checkpoints(
        result.setup, result.branches, [i.tick for _, planned, _ in plans for i in planned]
    )
    recording = Recording()
    records = []
    for goal, planned, skipped in plans:
        rows = []
        for intervention in planned:
            checkpoint = checkpoints[intervention.tick]
            player = intervention.action.player_id
            slot = next(i for i, p in enumerate(checkpoint.state.players) if p is not None and p.id == player)
            taus = tau_samples(result, checkpoint, slot, intervention.decision, samples, recording)
            if len(taus) == 0:
                skipped.append((intervention.action, "the decision did not come up again on replay"))
                continue
            rows.append(_row(intervention.action, intervention.decision, taus, feed))
        shot = _shot_for(actions, goal)
        records.append(
            {
                "goalEventId": feed.event_ids.get(goal.id),
                "shotEventId": feed.event_ids.get(shot.id) if shot else None,
                "scoringSide": "home" if goal.team == 0 else "away",
                "scorer": goal.player_id,
                "period": goal.period,
                "clockMs": goal.clock_ms,
                "actions": rows,
                "skipped": [
                    {"eventId": feed.event_ids.get(a.id), "type": a.kind, "reason": why} for a, why in skipped
                ],
                "verdict": verdict(rows),
            }
        )
    return records


def _oracle_match(job: tuple[int, int, Path, int, bool]) -> list[dict[str, Any]]:
    index, seed, out, samples, with_tracking = job
    league = build_league(DEFAULT_LEAGUE_SEED)
    home, away = fixture(league, index, seed)
    result = simulate_match(league, home, away, seed * 1000 + index)
    match_dir = out / "matches" / result.setup.match_id
    write_match(result, match_dir, with_tracking=with_tracking)
    feed = extract_events(result.setup.match_id, result.setup.seed, result.state.actions)
    return [
        {"matchId": result.setup.match_id, "matchDir": str(match_dir), **record}
        for record in attribute_goals(result, feed, samples)
    ]


def run_oracle(
    matches: int,
    seed: int,
    out: Path,
    samples: int = SAMPLES,
    workers: int | None = None,
    with_tracking: bool = False,
) -> dict[str, Any]:
    """Simulate `matches` matches, attribute every goal, and write oracle.jsonl and summary.json."""
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(index, seed, out, samples, with_tracking) for index in range(matches)]
    with ProcessPoolExecutor(max_workers=workers or os.cpu_count()) as pool:
        records = [record for part in pool.map(_oracle_match, jobs) for record in part]
    (out / "oracle.jsonl").write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in records))
    labels = Counter(r["verdict"]["label"] for r in records)
    summary = {
        "matches": matches,
        "seed": seed,
        "goals": len(records),
        "decisive": labels["decisive"],
        "shared": labels["shared"],
        "samplesPerOption": samples,
        "horizonSeconds": HORIZON_TICKS / 10,
        "actionsScored": sum(len(r["actions"]) for r in records),
        "actionsSkipped": sum(len(r["skipped"]) for r in records),
        "wallSeconds": round(time.perf_counter() - started, 1),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
