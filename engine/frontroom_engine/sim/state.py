"""Mutable match state and the small immutable records it holds while play is in progress.

Slots 0-10 are the home side and 11-21 the away side; slot 0 and slot 11 are the goalkeepers.
A substitution swaps the player in a slot, so per-slot trait arrays are part of the state.
"""

import copy
from dataclasses import dataclass, field

import numpy as np

from frontroom_engine.league.build import TRAIT_NAMES
from frontroom_engine.league.model import Player
from frontroom_engine.sim.records import Action, Decision, OffsideTruth, Point, ShotTruth, StoryBeat

SLOTS = 22


def team_slots(team: int) -> range:
    return range(11 * team, 11 * team + 11)


@dataclass(frozen=True)
class PendingPass:
    action_id: int
    kind: str
    passer: int
    receiver: int
    start: Point
    tick: int
    lofted: bool
    body_part: str
    offside: dict[int, float]


@dataclass(frozen=True)
class PendingShot:
    action_id: int
    kind: str
    shooter: int
    start: Point
    tick: int
    outcome: str
    resolve_tick: int
    keeper: int
    blocker: int
    body_part: str
    set_piece: str | None


@dataclass(frozen=True)
class Restart:
    kind: str
    team: int
    spot: Point
    ready_tick: int


@dataclass(frozen=True)
class UnflaggedOffside:
    action_id: int
    slot: int
    margin: float
    spot: Point


@dataclass
class MatchState:
    players: list[Player | None]
    traits: dict[str, np.ndarray]
    pos: np.ndarray
    vel: np.ndarray
    active: np.ndarray
    energy: np.ndarray
    drift: np.ndarray
    tick: int = 0
    period: int = 1
    period_start_tick: int = 0
    period_end_tick: int = 0
    phase: str = "dead"
    ball_pos: np.ndarray = field(default_factory=lambda: np.array([52.5, 34.0, 0.0]))
    ball_vel: np.ndarray = field(default_factory=lambda: np.zeros(3))
    ball_path: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    ball_path_vel: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    ball_history: np.ndarray = field(default_factory=lambda: np.tile([52.5, 34.0], (4, 1)))
    owner: int = -1
    last_touch: int = -1
    kicker_cooldown_until: int = 0
    launch_tick: int = 0
    possession_team: int = 0
    possession_id: int = 0
    next_decision_tick: int = 0
    carry_target: np.ndarray = field(default_factory=lambda: np.array([52.5, 34.0]))
    carry_speed: float = 0.0
    carry_start: Point = (52.5, 34.0)
    carry_start_tick: int = 0
    heavy_touch_until: int = 0
    take_on: tuple[int, int, int] | None = None
    """(action id, defender slot, deadline tick) while a take-on is being attempted."""
    pending_pass: PendingPass | None = None
    pending_shot: PendingShot | None = None
    restart: Restart | None = None
    set_piece: str | None = None
    """Restart kind that restricts and labels the carrier's next decision."""
    restart_taker: int = -1
    intercept_targets: dict[int, Point] = field(default_factory=dict)
    tackle_cooldown: np.ndarray = field(default_factory=lambda: np.zeros(SLOTS, dtype=int))
    press_cooldown: np.ndarray = field(default_factory=lambda: np.zeros(SLOTS, dtype=int))
    lapse_until: np.ndarray = field(default_factory=lambda: np.zeros(SLOTS, dtype=int))
    run_until: np.ndarray = field(default_factory=lambda: np.zeros(SLOTS, dtype=int))
    run_target: np.ndarray = field(default_factory=lambda: np.zeros((SLOTS, 2)))
    unflagged_offside: UnflaggedOffside | None = None
    score: list[int] = field(default_factory=lambda: [0, 0])
    yellow_cards: np.ndarray = field(default_factory=lambda: np.zeros(SLOTS, dtype=int))
    subs_made: list[int] = field(default_factory=lambda: [0, 0])
    substituted_in: list[str] = field(default_factory=list)
    sub_windows: list[list[int]] = field(default_factory=lambda: [[], []])
    next_action_id: int = 0
    actions: list[Action] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    shots: list[ShotTruth] = field(default_factory=list)
    offsides: list[OffsideTruth] = field(default_factory=list)
    beats: list[StoryBeat] = field(default_factory=list)

    def clone(self) -> "MatchState":
        """Copy for checkpointing. Records are immutable, so their lists are copied shallowly."""
        twin = copy.copy(self)
        for name, value in vars(self).items():
            if isinstance(value, np.ndarray):
                setattr(twin, name, value.copy())
            elif isinstance(value, list):
                setattr(twin, name, copy.deepcopy(value) if name == "sub_windows" else list(value))
            elif isinstance(value, dict):
                setattr(
                    twin, name, {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in value.items()}
                )
        return twin

    def new_action_id(self) -> int:
        self.next_action_id += 1
        return self.next_action_id

    def player_id(self, slot: int) -> str:
        player = self.players[slot]
        if player is None:
            raise ValueError(f"slot {slot} is empty")
        return player.id

    def set_player(self, slot: int, player: Player | None) -> None:
        self.players[slot] = player
        if player is not None:
            for name in TRAIT_NAMES:
                self.traits[name][slot] = getattr(player.traits, name)


def initial_state(home: tuple[Player, ...], away: tuple[Player, ...]) -> MatchState:
    traits = {name: np.zeros(SLOTS) for name in TRAIT_NAMES}
    state = MatchState(
        players=[None] * SLOTS,
        traits=traits,
        pos=np.zeros((SLOTS, 2)),
        vel=np.zeros((SLOTS, 2)),
        active=np.ones(SLOTS, dtype=bool),
        energy=np.ones(SLOTS),
        drift=np.zeros((SLOTS, 2)),
    )
    for slot, player in enumerate((*home, *away)):
        state.set_player(slot, player)
    return state
