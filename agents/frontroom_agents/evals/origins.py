"""Is the value model right about who made a goal? Graded against the simulator's ground truth.

The engine's oracle (`python -m frontroom_engine oracle`, engine/ORACLE.md) replays each goal's possession
with every on-ball action swapped for the alternatives that player actually had, on paired noise, and
measures each action's true advantage over a typical choice (tau). Here the production estimator (expected
threat fitted on real Premier League data, origins/xt.py) runs on the same goals exactly as it runs live,
from the noisy event feed, and is compared with tau:

- Ranking: Spearman correlation between our credit and tau over the actions both scored, per goal.
- Strongest action: how often we pick the action with the largest tau, against three baselines: credit
  the last pass before the shot (the assist), credit the action that won the ball, and pick at random.
- Verdict: agreement on "decisive" versus "shared". The rule's floor and margin are calibrated on one
  oracle run (one set of matches) and then tested, untouched, on another.

What it found decided what the TV may say: see DECISIVE_ON_AIR in origins/workflow.py.

    uv run python -m frontroom_agents.evals.origins \
        data/generated/oracle-2 --calibrate-on data/generated/oracle
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

from ..origins.chain import SHOTS, credit, scoring_possession, verdict
from ..origins.xt import ExpectedThreat
from ..server.engine_source import load_match

ROOT = Path(__file__).resolve().parents[3]
RESULTS = Path(__file__).with_name("origins-results.json")


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = mean(ra), mean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else None


def top_and_gap(credits: list) -> tuple[float, float]:
    """Our biggest single credit outside the shot, and how far it leads the next."""
    values = sorted((c.value for c in credits if c.type not in SHOTS), reverse=True)
    if not values:
        return (0.0, 0.0)
    return (values[0], values[0] - (values[1] if len(values) > 1 else 0.0))


def balanced_accuracy(rows: list[dict], floor: float, margin: float) -> dict:
    """How well "decisive when the top credit clears the floor and leads by the margin" matches the oracle."""
    called = [r["top"][0] >= floor and r["top"][1] >= margin for r in rows]
    truth = [r["oracle_verdict"] == "decisive" for r in rows]
    tp = sum(c and t for c, t in zip(called, truth, strict=True))
    tn = sum(not c and not t for c, t in zip(called, truth, strict=True))
    pos, neg = sum(truth), len(truth) - sum(truth)
    return {
        "floor": floor,
        "margin": margin,
        "balanced_accuracy": round(((tp / pos if pos else 0) + (tn / neg if neg else 0)) / 2, 3),
        "decisive_found": f"{tp}/{pos}",
        "shared_kept_shared": f"{tn}/{neg}",
    }


def calibrate(fit_rows: list[dict], test_rows: list[dict]) -> dict:
    grid = [(f / 100, m / 100) for f in range(3, 31) for m in range(0, 16)]
    best = max(grid, key=lambda fm: (balanced_accuracy(fit_rows, *fm)["balanced_accuracy"], fm[0], fm[1]))
    return {
        "current_rule_on_test": balanced_accuracy(test_rows, 0.05, 0.0),
        "fitted_on_calibration_run": balanced_accuracy(fit_rows, *best),
        "fitted_rule_on_test": balanced_accuracy(test_rows, *best),
    }


def grade(oracle_dir: Path) -> dict:
    model = ExpectedThreat()
    goals = [json.loads(line) for line in (oracle_dir / "oracle.jsonl").read_text().splitlines() if line]
    matches: dict[str, object] = {}
    rows = []
    for goal in goals:
        match_dir = ROOT / goal["matchDir"]
        source = matches.setdefault(goal["matchId"], load_match(match_dir))
        events = source.events  # type: ignore[attr-defined]
        by_id = {e["id"]: e for e in events}
        if goal["shotEventId"] not in by_id:
            continue
        shot = by_id[goal["shotEventId"]]
        attacking_right = shot.get("end", shot["start"])["x"] > shot["start"]["x"]
        chain = scoring_possession(events, goal["shotEventId"])
        ours = {c.event_id: c for c in credit(chain, model, attacking_right)}
        truth = {a["eventId"]: a for a in goal["actions"]}
        common = [i for i in truth if i in ours]
        if len(common) < 2:
            continue
        tau = [truth[i]["tau"] for i in common]
        est = [ours[i].value for i in common]
        best = max(common, key=lambda i: truth[i]["tau"])
        moves = [i for i in common if by_id[i]["type"] in ("pass", "cross") and i != goal["shotEventId"]]
        rows.append(
            {
                "goal": goal["goalEventId"],
                "match": goal["matchId"],
                "actions": len(common),
                "spearman": spearman(est, tau),
                "ours_top": max(common, key=lambda i: ours[i].value) == best,
                "assist_top": bool(moves) and moves[-1] == best,
                "regain_top": common[0] == best,
                "random_top": 1 / len(common),
                "oracle_verdict": goal["verdict"]["label"],
                "our_verdict": verdict(list(ours.values())).kind,
                "top": top_and_gap(list(ours.values())),
            }
        )

    correlated = [r["spearman"] for r in rows if r["spearman"] is not None]
    n = len(rows)
    decisive = [r for r in rows if r["oracle_verdict"] == "decisive"]
    agree = sum(r["oracle_verdict"] == r["our_verdict"] for r in rows)
    return {
        "_rows": rows,
        "goals_in_oracle": len(goals),
        "goals_graded": n,
        "mean_actions_per_goal": round(mean(r["actions"] for r in rows), 1),
        "spearman_mean": round(mean(correlated), 3),
        "spearman_positive_share": round(sum(c > 0 for c in correlated) / len(correlated), 3),
        "strongest_action": {
            "ours": round(sum(r["ours_top"] for r in rows) / n, 3),
            "assist_baseline": round(sum(r["assist_top"] for r in rows) / n, 3),
            "regain_baseline": round(sum(r["regain_top"] for r in rows) / n, 3),
            "random_baseline": round(mean(r["random_top"] for r in rows), 3),
        },
        "strongest_action_on_oracle_decisive_goals": {
            "goals": len(decisive),
            "ours": round(sum(r["ours_top"] for r in decisive) / len(decisive), 3) if decisive else None,
        },
        "verdict_agreement": round(agree / n, 3),
        "verdicts": {
            f"oracle {o}, ours {u}": sum(r["oracle_verdict"] == o and r["our_verdict"] == u for r in rows)
            for o in ("decisive", "shared")
            for u in ("decisive", "shared")
        },
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    test_dir = ROOT / (args[0] if args else "data/generated/oracle")
    results = grade(test_dir)
    test_rows = results.pop("_rows")
    if "--calibrate-on" in args:
        fit = grade(ROOT / args[args.index("--calibrate-on") + 1])
        results["calibration"] = calibrate(fit.pop("_rows"), test_rows)
    RESULTS.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
