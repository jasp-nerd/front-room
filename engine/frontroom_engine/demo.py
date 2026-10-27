"""The demo match: Kestrel FC v Ashvale Athletic.

The story the product is built around: an Ashvale goal ruled out by VAR for offside just
before the hour, then Kestrel's goal by Okafor (#9) around 63', which started about 18 seconds
earlier when Mensah (#6) pressed Lund (#4) near halfway and won the ball, followed by four or so
passes. Each beat is a test over the action log; `scenario.steer` finds a future in which they
all happen, and the resulting branch schedule is saved as a recipe so the match replays exactly.
"""

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from frontroom_engine.league import DEFAULT_LEAGUE_SEED, League, build_league
from frontroom_engine.scenario import (
    Beat,
    SteeringReport,
    action_minute,
    at_minute,
    beat_tick,
    steer,
    wait_until,
    within,
)
from frontroom_engine.sim.core import Simulator
from frontroom_engine.sim.geometry import attack_sign
from frontroom_engine.sim.match import MatchResult, create_simulator, finish
from frontroom_engine.sim.noise import NoiseTape
from frontroom_engine.sim.offball import offside_line
from frontroom_engine.sim.records import Action, DetailValue, StoryBeat
from frontroom_engine.sim.setup import make_setup

DEMO_SEED = 7
HOME, AWAY = 0, 1
MENSAH, OKAFOR, DIALLO, LUND = "kes-06-mensah", "kes-09-okafor", "kes-10-diallo", "ash-04-lund"
RECIPE_PATH = Path(__file__).with_name("demo_recipe.json")
HALFWAY_BAND = 15.0
PRESS_WINDOW = (60.5, 63.0)
TURNOVER_TICKS = 40
PASSES_IN_MOVE = (3, 6)
SECONDS_TO_GOAL = (10.0, 28.0)
FINAL_THIRD = 70.0
OFFSIDE_WINDOW = (56.5, 59.0)
DISALLOWED_GOAL_BY = 59.5
TIGHT_OFFSIDE = 0.6

Found = dict[str, DetailValue] | None


def _slot_of(sim: Simulator, player_id: str) -> int:
    return next(slot for slot, p in enumerate(sim.state.players) if p is not None and p.id == player_id)


def _attacking_x(x: float, team: int, period: int) -> float:
    return x if attack_sign(team, period) > 0 else 105.0 - x


def _beat(beats: Sequence[StoryBeat], name: str) -> StoryBeat | None:
    return next((b for b in beats if b.name == name), None)


def _offside_missed(actions: Sequence[Action], beats: Sequence[StoryBeat]) -> Found:
    """An Ashvale pass received in an offside position that the assistant referee did not flag."""
    for action in actions:
        final_third = (
            action.end is not None and _attacking_x(action.end[0], AWAY, action.period) >= FINAL_THIRD
        )
        if (
            action.team == AWAY
            and "offsideMargin" in action.latent
            and final_third
            and OFFSIDE_WINDOW[0] <= action_minute(action) <= OFFSIDE_WINDOW[1]
        ):
            return {
                "offsidePassAction": action.id,
                "possession": action.possession,
                "margin": action.latent["offsideMargin"],
            }
    return None


def _ashvale_attack(sim: Simulator) -> float:
    s = sim.state
    if s.possession_team != AWAY:
        return 0.0
    depth = float(sim.relative(s.ball_pos[:2], AWAY)[0]) / 105.0
    shooting = 1.0 if s.pending_shot is not None and s.pending_shot.shooter // 11 == AWAY else 0.0
    return depth + shooting


def _line_beaters(sim: Simulator) -> float:
    """Ashvale building an attack with a forward just beyond Kestrel's last line: a tight call waiting."""
    s = sim.state
    pending = s.pending_pass
    if pending is not None and pending.passer // 11 == AWAY:
        tight_target = 0.0 < pending.offside.get(pending.receiver, 0.0) < TIGHT_OFFSIDE
        return _ashvale_attack(sim) + (2.0 if tight_target else 0.0)
    if s.possession_team != AWAY or s.owner < 0:
        return _ashvale_attack(sim)
    line = offside_line(s, AWAY, sim.sign(AWAY))
    margins = [
        float(sim.relative(s.pos[slot], AWAY)[0]) - line for slot in sim.active_slots(AWAY) if slot != s.owner
    ]
    tight = sum(1 for m in margins if 0.0 < m < TIGHT_OFFSIDE)
    return _ashvale_attack(sim) + 0.7 * tight


def _possession_continues(sim: Simulator, detail: dict[str, DetailValue]) -> bool:
    s = sim.state
    return s.phase == "play" and s.possession_id == int(detail["possession"])


def _offside_attack(sim: Simulator) -> float:
    offside = _beat(sim.state.beats, "offside_missed")
    if offside is None or sim.state.possession_id != int(offside.detail["possession"]):
        return -1.0
    return _ashvale_attack(sim)


def _disallowed_goal(actions: Sequence[Action], beats: Sequence[StoryBeat]) -> Found:
    offside = _beat(beats, "offside_missed")
    if offside is None:
        return None
    by_id = {a.id: a for a in actions}
    for decision in actions:
        if decision.kind == "var_decision" and decision.result == "offside" and decision.team == AWAY:
            goal = by_id.get(int(decision.detail["goalAction"]))
            if (
                goal is not None
                and goal.possession == int(offside.detail["possession"])
                and OFFSIDE_WINDOW[0] <= action_minute(goal) <= DISALLOWED_GOAL_BY
            ):
                return {"goalAction": goal.id, "varDecisionAction": decision.id, "scorer": goal.player_id}
    return None


def _turnover_after(actions: Sequence[Action], press: Action) -> Action | None:
    """The Kestrel action that took the ball off Lund within a few seconds of the press, if any."""
    window = [a for a in actions if press.tick <= a.tick <= press.tick + TURNOVER_TICKS]
    for action in window:
        if action.kind == "tackle" and action.result == "success" and action.detail.get("onPlayer") == LUND:
            return action if action.team == HOME else None
        if action.kind == "interception" and action.team == HOME:
            lost_by = next(
                (
                    a
                    for a in reversed(actions)
                    if a.tick < action.tick and a.team == AWAY and a.kind == "pass"
                ),
                None,
            )
            return action if lost_by is not None and lost_by.player_id == LUND else None
    return None


def _press_win(actions: Sequence[Action], beats: Sequence[StoryBeat]) -> Found:
    """Mensah presses Lund near halfway and Kestrel win the ball off Lund straight after."""
    for press in actions:
        if not (
            press.kind == "press"
            and press.player_id == MENSAH
            and press.detail.get("onPlayer") == LUND
            and PRESS_WINDOW[0] <= action_minute(press) <= PRESS_WINDOW[1]
            and press.end is not None
            and abs(press.end[0] - 52.5) <= HALFWAY_BAND
        ):
            continue
        won = _turnover_after(actions, press)
        if won is None:
            continue
        follow_up = next(
            (a for a in actions if a.tick > won.tick and a.kind in ("pass", "dribble", "cross", "shot")), None
        )
        if follow_up is None or follow_up.team != HOME or follow_up.tick - won.tick > 30:
            continue
        return {
            "pressAction": press.id,
            "winAction": won.id,
            "possession": follow_up.possession,
            "winTick": won.tick,
        }
    return None


def _win_ball_from_lund(sim: Simulator) -> float:
    """Ashvale working the ball to Lund near halfway, with Mensah close enough to press him."""
    s = sim.state
    if s.possession_team != AWAY:
        return 0.0
    lund, mensah = _slot_of(sim, LUND), _slot_of(sim, MENSAH)
    closing = max(0.0, 1.0 - float(np.linalg.norm(s.pos[mensah] - s.pos[lund])) / 25.0)
    halfway = 1.0 - min(1.0, abs(float(s.pos[lund][0]) - 52.5) / 30.0)
    if s.pending_pass is not None and s.pending_pass.receiver == lund:
        return 1.0 + halfway + closing
    if s.owner == lund:
        return 1.5 + halfway + 2.0 * closing
    near_lund = max(0.0, 1.0 - float(np.linalg.norm(s.ball_pos[:2] - s.pos[lund])) / 30.0)
    return 0.2 + 0.5 * near_lund + 0.3 * halfway


def _story_goal(actions: Sequence[Action], beats: Sequence[StoryBeat]) -> Found:
    win = _beat(beats, "press_win")
    if win is None:
        return None
    possession = int(win.detail["possession"])
    for goal in actions:
        if (
            goal.kind != "goal"
            or goal.player_id != OKAFOR
            or goal.result != "success"
            or goal.possession != possession
        ):
            continue
        if any(a.kind == "var_decision" and a.detail.get("goalAction") == goal.id for a in actions):
            continue
        passes = [
            a.id
            for a in actions
            if a.kind in ("pass", "cross")
            and a.result == "success"
            and a.possession == possession
            and a.team == HOME
            and a.tick < goal.tick
        ]
        seconds = (goal.tick - int(win.detail["winTick"])) / 10
        if (
            PASSES_IN_MOVE[0] <= len(passes) <= PASSES_IN_MOVE[1]
            and SECONDS_TO_GOAL[0] <= seconds <= SECONDS_TO_GOAL[1]
        ):
            return {
                "goalAction": goal.id,
                "passes": len(passes),
                "secondsFromWin": seconds,
                "passActions": ",".join(map(str, passes)),
            }
    return None


def _towards_okafor_goal(sim: Simulator) -> float:
    s = sim.state
    win = _beat(s.beats, "press_win")
    if s.possession_id != int(win.detail["possession"]):
        return -1.0
    okafor = _slot_of(sim, OKAFOR)
    depth = float(sim.relative(s.ball_pos[:2], HOME)[0]) / 105.0
    passes = sum(
        1
        for a in s.actions
        if a.kind in ("pass", "cross") and a.result == "success" and a.possession == s.possession_id
    )
    involved = (
        0.5
        if s.owner == okafor or (s.pending_pass is not None and s.pending_pass.receiver == okafor)
        else 0.0
    )
    shooting = 1.0 if s.pending_shot is not None and s.pending_shot.shooter == okafor else 0.0
    return depth + 0.15 * min(passes, 4) + involved + shooting


DEMO_BEATS = [
    Beat(
        "offside_missed",
        wait_until(OFFSIDE_WINDOW[0]),
        at_minute(OFFSIDE_WINDOW[1]),
        _line_beaters,
        _offside_missed,
        _possession_continues,
    ),
    Beat("var_disallowed_goal", lambda sim: None, within(25.0), _offside_attack, _disallowed_goal),
    Beat(
        "press_win",
        wait_until(PRESS_WINDOW[0]),
        at_minute(PRESS_WINDOW[1]),
        _win_ball_from_lund,
        _press_win,
        _possession_continues,
    ),
    Beat("okafor_goal", lambda sim: None, within(SECONDS_TO_GOAL[1]), _towards_okafor_goal, _story_goal),
]


def demo_simulator(league: League, branches: tuple[tuple[int, int], ...] = ()) -> Simulator:
    setup = make_setup(league, "KES", "ASH", DEMO_SEED, kept_on=frozenset({MENSAH, OKAFOR, DIALLO, LUND}))
    return create_simulator(setup, NoiseTape(DEMO_SEED, branches))


def story_in(actions: Sequence[Action]) -> list[StoryBeat]:
    """Re-derive the demo beats from a finished match's action log; empty if any beat is missing."""
    ordered = sorted(actions, key=lambda a: (a.tick, a.id))
    beats: list[StoryBeat] = []
    for beat in DEMO_BEATS:
        detail = beat.found(ordered, beats)
        if detail is None:
            return []
        beats.append(StoryBeat(beat.name, beat_tick(ordered, detail), detail))
    return beats


def search_demo(league: League) -> tuple[MatchResult, SteeringReport]:
    sim = demo_simulator(league)
    report = steer(sim, DEMO_BEATS)
    result = finish(sim)
    RECIPE_PATH.write_text(
        json.dumps(
            {
                "seed": DEMO_SEED,
                "leagueSeed": league.seed,
                "branches": [list(branch) for branch in result.branches],
                "steering": report.as_dict(),
            },
            indent=2,
        )
        + "\n"
    )
    return result, report


def demo_match(league: League | None = None) -> tuple[MatchResult, dict[str, float | int]]:
    """Replay the saved recipe; search again (and resave it) if the engine no longer produces the story."""
    league = league or build_league(DEFAULT_LEAGUE_SEED)
    if RECIPE_PATH.exists():
        recipe = json.loads(RECIPE_PATH.read_text())
        branches = tuple((int(tick), int(salt)) for tick, salt in recipe["branches"])
        result = finish(demo_simulator(league, branches))
        beats = story_in(result.state.actions)
        if beats:
            result.state.beats.extend(beats)
            return result, recipe["steering"]
    result, report = search_demo(league)
    return result, report.as_dict()
