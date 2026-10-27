"""Immutable records the simulator appends while a match runs.

`Action` is the simulator's own account of what happened on the ball; the event extractor turns
actions into feed events. `Decision` and `ShotTruth` are latent truth that no feed consumer sees:
the options a player weighed and the physical chance a shot really had.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

Point = tuple[float, float]
DetailValue = str | float | bool


@dataclass(frozen=True)
class Action:
    id: int
    tick: int
    period: int
    clock_ms: int
    kind: str
    slot: int
    player_id: str
    team: int
    start: Point
    end: Point | None = None
    result: str = "none"
    body_part: str = "foot"
    possession: int = 0
    end_tick: int | None = None
    detail: Mapping[str, DetailValue] = field(default_factory=dict)
    latent: Mapping[str, DetailValue] = field(default_factory=dict)
    """Truth about this action that the feed never shows, such as an unflagged offside margin."""


@dataclass(frozen=True)
class OptionRecord:
    kind: str
    target_player: str | None
    end: Point
    utility: float
    perceived_success: float


@dataclass(frozen=True)
class Decision:
    action_id: int
    tick: int
    player_id: str
    options: tuple[OptionRecord, ...]
    probabilities: tuple[float, ...]
    chosen: int


@dataclass(frozen=True)
class ShotTruth:
    action_id: int
    tick: int
    team: int
    xg: float
    """Monte Carlo P(goal) under the simulator's own shot physics, given the state at release."""
    outcome: str
    distance: float
    pressure: float
    on_target_probability: float


@dataclass(frozen=True)
class OffsideTruth:
    action_id: int
    receiver_id: str
    margin: float
    flagged: bool


@dataclass(frozen=True)
class StoryBeat:
    name: str
    tick: int
    detail: Mapping[str, DetailValue] = field(default_factory=dict)
