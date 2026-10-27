"""How a passage of play ends: shots, the ball leaving the pitch, goals and VAR reviews."""

import numpy as np

from frontroom_engine.pitch import CENTRE_X, CENTRE_Y, GOAL_HEIGHT, GOAL_WIDTH, PITCH_LENGTH, PITCH_WIDTH
from frontroom_engine.sim.ball import rotate
from frontroom_engine.sim.core import Simulator, point
from frontroom_engine.sim.launch import launch
from frontroom_engine.sim.possession import fail_pass, gain_control
from frontroom_engine.sim.records import ShotTruth
from frontroom_engine.sim.restarts import begin_restart
from frontroom_engine.sim.setup import HOME_EDGE
from frontroom_engine.sim.shots import (
    BLOCKED,
    OUTCOMES,
    PARRIED,
    SAVED,
    ShotSituation,
    expected_goal,
    resolve_shots,
    uniform_columns,
)
from frontroom_engine.sim.state import PendingShot

BLOCKER_RANGE = 25.0
VAR_CHECK_DELAY = 150
VAR_DECISION_DELAY = 700
GOAL_AREA_DEPTH = 5.5
GOAL_AREA_HALF_WIDTH = 9.16
TIP_BEHIND_QUANTILE = 0.3
TIP_BEHIND_DEPTH = 6.0
"""Standard-normal threshold: a little under 40 % of parries and punches go behind for a corner."""


def take_shot(
    sim: Simulator,
    shooter: int,
    action_id: int,
    *,
    header: bool = False,
    kind: str = "shot",
    set_piece: str | None = None,
) -> None:
    s = sim.state
    team = shooter // 11
    goal_x = PITCH_LENGTH if sim.sign(team) > 0 else 0.0
    keeper = sim.keeper(1 - team)
    start = s.ball_pos.copy()
    if not header:
        start[2] = 0.11
    shooter_x = sim.relative(s.pos[shooter], team)[0]
    rivals = [r for r in sim.active_slots(1 - team) if r != keeper]
    blockers = [
        r
        for r in rivals
        if np.linalg.norm(s.pos[r] - s.pos[shooter]) < BLOCKER_RANGE
        and sim.relative(s.pos[r], team)[0] > shooter_x - 1.0
    ]
    nearest = min(float(np.linalg.norm(s.pos[r] - s.pos[shooter])) for r in rivals)
    pressure = float(np.clip((3.5 - nearest) / 3.5, 0.0, 1.0))
    situation = ShotSituation(
        start=start,
        goal_x=goal_x,
        keeper_pos=s.pos[keeper].copy(),
        keeper_reaction=float(s.traits["reaction_time"][keeper]),
        keeper_skill=float(s.traits["goalkeeping"][keeper]),
        blockers=s.pos[blockers].copy() if blockers else np.zeros((0, 2)),
        finishing=float(s.traits["finishing"][shooter]) * (1.0 - HOME_EDGE if team == 0 else 1.0),
        pressure=pressure,
        header=header,
        penalty=kind == "penalty",
    )
    rng = sim.tape.generator("shot", s.tick, shooter)
    batch = resolve_shots(
        situation, rng.standard_normal((1, 3)), rng.random((1, uniform_columns(len(blockers))))
    )
    xg, on_target = expected_goal(situation, np.random.default_rng([sim.setup.seed, s.tick, shooter]))
    code = int(batch.outcome[0])
    if s.owner == shooter:
        sim.log_carry(shooter)
    distance = float(np.hypot(goal_x - start[0], CENTRE_Y - start[1]))
    s.shots.append(
        ShotTruth(
            action_id,
            s.tick,
            team,
            round(xg, 4),
            OUTCOMES[code],
            round(distance, 2),
            round(pressure, 3),
            round(on_target, 4),
        )
    )
    resolves_early = code in (SAVED, PARRIED, BLOCKED)
    resolve_tick = s.tick + int(batch.resolve_step[0]) + 1 if resolves_early else -1
    blocker = blockers[int(batch.blocker[0])] if code == BLOCKED else -1
    s.pending_pass = None
    s.pending_shot = PendingShot(
        action_id,
        kind,
        shooter,
        point(start),
        s.tick,
        OUTCOMES[code],
        resolve_tick,
        keeper,
        blocker,
        "head" if header else "foot",
        set_piece if kind == "shot" else None,
    )
    s.ball_pos = start
    launch(sim, batch.velocity[0], shooter)
    keeper_step = (
        int(batch.resolve_step[0])
        if code in (SAVED, PARRIED)
        else int(np.argmin(np.linalg.norm(s.ball_path[:20, :2] - s.pos[keeper], axis=1)))
    )
    s.intercept_targets = {keeper: point(s.ball_path[keeper_step, :2])}


def shot_detail(shot: PendingShot, outcome: str) -> dict[str, str]:
    return {"outcome": outcome, "setPiece": shot.set_piece} if shot.set_piece else {"outcome": outcome}


def resolve_shot(sim: Simulator) -> None:
    """Play out a block or a save at the moment the ball reaches the blocker or the keeper."""
    s = sim.state
    shot = s.pending_shot
    s.pending_shot = None
    here = s.ball_pos[:2].copy()
    sim.act(
        shot.kind,
        shot.shooter,
        shot.start,
        end=here,
        result="fail",
        body_part=shot.body_part,
        action_id=shot.action_id,
        tick=shot.tick,
        detail=shot_detail(shot, shot.outcome),
    )
    if shot.outcome == "blocked":
        n = sim.tape.normal("shot", s.tick, shot.blocker)
        deflected = rotate(s.ball_vel, 0.9 * n[0]) * 0.5
        deflected[2] = 1.0 + 2.0 * abs(n[1])
        launch(sim, deflected, shot.blocker)
        return
    sim.act(
        "keeper_save",
        shot.keeper,
        here,
        result="success",
        body_part="other",
        detail={"outcome": "caught" if shot.outcome == "saved" else "parried"},
    )
    if shot.outcome == "saved":
        gain_control(sim, shot.keeper)
        return
    launch(sim, parry_velocity(sim, shot.keeper), shot.keeper)


def parry_velocity(sim: Simulator, keeper: int) -> np.ndarray:
    """Push the ball wide: either back into play or behind for a corner, never into the goal mouth."""
    s = sim.state
    n = sim.tape.normal("keeper", s.tick, keeper)
    own_goal_x = 0.0 if sim.sign(keeper // 11) > 0 else PITCH_LENGTH
    offset = s.ball_pos[1] - CENTRE_Y
    side = np.sign(offset) if abs(offset) > 0.5 else (1.0 if n[1] >= 0 else -1.0)
    behind = n[2] > TIP_BEHIND_QUANTILE and abs(own_goal_x - s.ball_pos[0]) < TIP_BEHIND_DEPTH
    to_line = (own_goal_x - s.ball_pos[0]) if behind else -np.sign(own_goal_x - CENTRE_X) * 4.0
    lateral = side * (GOAL_WIDTH / 2 + 2.0 - abs(offset) + 3.0 * abs(n[1]))
    flight = 0.5
    return np.array([to_line / flight, lateral / flight, 2.5])


def _close_attempts(sim: Simulator, end: np.ndarray) -> None:
    s = sim.state
    shot = s.pending_shot
    if shot is not None:
        s.pending_shot = None
        sim.act(
            shot.kind,
            shot.shooter,
            shot.start,
            end=end,
            result="fail",
            body_part=shot.body_part,
            action_id=shot.action_id,
            tick=shot.tick,
            detail=shot_detail(shot, "off_target"),
        )
    fail_pass(sim, end)


def _goal(sim: Simulator, scoring_team: int, end: np.ndarray) -> None:
    s = sim.state
    shot = s.pending_shot
    if shot is not None:
        s.pending_shot = None
        scorer = shot.shooter
        sim.act(
            shot.kind,
            scorer,
            shot.start,
            end=end,
            result="success",
            body_part=shot.body_part,
            action_id=shot.action_id,
            tick=shot.tick,
            detail=shot_detail(shot, "goal"),
        )
    else:
        scorer = s.last_touch
        fail_pass(sim, end)
    own_goal = scorer // 11 != scoring_team
    goal = sim.act(
        "goal",
        scorer,
        end,
        result="own_goal" if own_goal else "success",
        detail={"scoringSide": "home" if scoring_team == 0 else "away"},
    )
    offside = s.unflagged_offside
    if offside is not None and not own_goal and s.possession_team == scoring_team:
        sim.act(
            "var_check",
            scorer,
            end,
            tick=s.tick + VAR_CHECK_DELAY,
            detail={"reason": "possible offside", "goalAction": goal.id},
        )
        sim.act(
            "var_decision",
            scorer,
            end,
            tick=s.tick + VAR_DECISION_DELAY,
            result="offside",
            detail={
                "outcome": "goal disallowed",
                "reason": "offside",
                "margin": round(offside.margin, 2),
                "offsidePlayer": s.player_id(offside.slot),
                "goalAction": goal.id,
                "passAction": offside.action_id,
            },
        )
        begin_restart(sim, "free_kick", 1 - scoring_team, np.array(offside.spot), reason="var")
        return
    s.score[scoring_team] += 1
    begin_restart(sim, "kick_off", 1 - scoring_team, np.array([CENTRE_X, CENTRE_Y]), reason="goal")


def crossed_boundary(sim: Simulator, previous: np.ndarray) -> bool:
    """Handle the ball leaving the pitch this tick: a goal, a corner, a goal kick or a throw-in."""
    s = sim.state
    x, y = s.ball_pos[:2]
    if 0.0 <= x <= PITCH_LENGTH and 0.0 <= y <= PITCH_WIDTH:
        return False
    if x < 0.0 or x > PITCH_LENGTH:
        line_x = 0.0 if x < 0.0 else PITCH_LENGTH
        fraction = (line_x - previous[0]) / (x - previous[0])
        crossing = previous + fraction * (s.ball_pos - previous)
        end = np.array([line_x, np.clip(crossing[1], 0.0, PITCH_WIDTH)])
        attacking = 0 if sim.sign(0) == (1 if line_x == PITCH_LENGTH else -1) else 1
        if abs(crossing[1] - CENTRE_Y) < GOAL_WIDTH / 2 and crossing[2] < GOAL_HEIGHT:
            _goal(sim, attacking, end)
            return True
        _close_attempts(sim, end)
        inward = 1.0 if line_x == 0.0 else -1.0
        if s.last_touch // 11 == attacking:
            spot = np.array(
                [
                    line_x + inward * GOAL_AREA_DEPTH,
                    CENTRE_Y + GOAL_AREA_HALF_WIDTH * np.sign(crossing[1] - CENTRE_Y),
                ]
            )
            begin_restart(sim, "goal_kick", 1 - attacking, spot)
        else:
            spot = np.array([line_x + inward * 0.3, 0.3 if crossing[1] < CENTRE_Y else PITCH_WIDTH - 0.3])
            begin_restart(sim, "corner", attacking, spot)
        return True
    line_y = 0.0 if y < 0.0 else PITCH_WIDTH
    fraction = (line_y - previous[1]) / (y - previous[1])
    crossing_x = float(np.clip(previous[0] + fraction * (x - previous[0]), 0.5, PITCH_LENGTH - 0.5))
    _close_attempts(sim, np.array([crossing_x, line_y]))
    begin_restart(sim, "throw_in", 1 - s.last_touch // 11, np.array([crossing_x, line_y]))
    return True
