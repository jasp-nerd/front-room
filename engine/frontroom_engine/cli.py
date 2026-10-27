"""Command line: generate a match, run the realism scorecard, build the demo, refresh calibration."""

import argparse
import json
import time
from pathlib import Path

from frontroom_engine.calibration.reference import write_reference
from frontroom_engine.calibration.scorecard import fixture, markdown, scorecard
from frontroom_engine.demo import demo_match, search_demo
from frontroom_engine.io import write_match
from frontroom_engine.league import DEFAULT_LEAGUE_SEED, build_league
from frontroom_engine.oracle import run_oracle
from frontroom_engine.sim.match import simulate_match


def _generate(args: argparse.Namespace) -> None:
    league = build_league(args.league_seed)
    home, away = (args.home, args.away) if args.home and args.away else fixture(league, 0, args.seed)
    started = time.perf_counter()
    result = simulate_match(league, home, away, args.seed)
    files = write_match(result, args.out)
    home_goals, away_goals = result.state.score
    print(
        f"{result.setup.match_id}: {home} {home_goals}-{away_goals} {away} "
        f"in {time.perf_counter() - started:.1f}s -> {files.metadata.parent}"
    )


def _scorecard(args: argparse.Namespace) -> None:
    report = scorecard(args.matches, args.seed, args.workers)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "scorecard.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.out / "scorecard.md").write_text(markdown(report))
    print(markdown(report))


def _demo(args: argparse.Namespace) -> None:
    league = build_league(DEFAULT_LEAGUE_SEED)
    if args.search:
        result, report = search_demo(league)
        steering = report.as_dict()
    else:
        result, steering = demo_match(league)
    files = write_match(result, args.out, steering)
    home_goals, away_goals = result.state.score
    print(f"{result.setup.match_id}: Kestrel FC {home_goals}-{away_goals} Ashvale Athletic")
    print(f"  written to {files.metadata.parent}")
    for beat in json.loads(files.truth.read_text())["story"]:
        minute = (beat["period"] - 1) * 45 + beat["clockMs"] / 60000
        print(f"  {beat['beat']} ({minute:.1f}'): {beat['events']}")


def _oracle(args: argparse.Namespace) -> None:
    summary = run_oracle(args.matches, args.seed, args.out, args.samples, args.workers, args.tracking)
    print(json.dumps(summary, indent=2))


def _calibrate(args: argparse.Namespace) -> None:
    reference = write_reference(args.raw)
    print(json.dumps(reference, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m frontroom_engine")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="simulate one match and write its files")
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--home", help="home club short code, e.g. KES")
    generate.add_argument("--away", help="away club short code, e.g. ASH")
    generate.add_argument("--league-seed", type=int, default=DEFAULT_LEAGUE_SEED)
    generate.add_argument("--out", type=Path, required=True)
    generate.set_defaults(run=_generate)

    card = commands.add_parser("scorecard", help="score N simulated matches against the open-data reference")
    card.add_argument("--matches", type=int, default=50)
    card.add_argument("--seed", type=int, default=1)
    card.add_argument("--workers", type=int)
    card.add_argument("--out", type=Path, default=Path("data/generated/scorecard"))
    card.set_defaults(run=_scorecard)

    demo = commands.add_parser("demo", help="write the Kestrel v Ashvale demo match")
    demo.add_argument("--out", type=Path, default=Path("data/generated/demo"))
    demo.add_argument(
        "--search", action="store_true", help="search for the storyline again instead of replaying"
    )
    demo.set_defaults(run=_demo)

    oracle = commands.add_parser("oracle", help="ground-truth origins of every goal in N simulated matches")
    oracle.add_argument("--matches", type=int, default=35)
    oracle.add_argument("--seed", type=int, default=1)
    oracle.add_argument("--samples", type=int, default=8, help="paired futures per option")
    oracle.add_argument("--workers", type=int)
    oracle.add_argument("--tracking", action="store_true", help="also write tracking.parquet per match")
    oracle.add_argument("--out", type=Path, default=Path("data/generated/oracle"))
    oracle.set_defaults(run=_oracle)

    calibrate = commands.add_parser("calibrate", help="recompute reference_stats.json from data/raw")
    calibrate.add_argument("--raw", type=Path, default=Path("data/raw"))
    calibrate.set_defaults(run=_calibrate)

    args = parser.parse_args(argv)
    args.run(args)
    return 0
