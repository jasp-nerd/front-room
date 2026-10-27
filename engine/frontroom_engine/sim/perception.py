"""What a ball carrier perceives: his attacking-frame view of the pitch, limited by scanning.

Opponents behind him and beyond his scan radius are invisible to his pass judgements, though
they still exist physically. That gap between perception and physics is where misjudged passes
come from, and it is the reason scan radius is a meaningful planted skill.
"""

from dataclasses import dataclass

import numpy as np

from frontroom_engine.pitch import CENTRE_Y, PITCH_LENGTH
from frontroom_engine.sim.geometry import attack_sign, threat, to_attack_frame
from frontroom_engine.sim.motion import time_to_reach
from frontroom_engine.sim.state import MatchState, team_slots

PERIPHERAL_RADIUS = 8.0
"""Opponents this close are sensed whichever way the carrier faces."""


def sigmoid(x: np.ndarray | float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


@dataclass
class CarrierView:
    """The carrier's situation in his attacking frame, restricted to what he can perceive."""

    state: MatchState
    carrier: int
    team: int
    pos: np.ndarray
    facing: np.ndarray
    mates: np.ndarray
    mate_pos: np.ndarray
    mate_vel: np.ndarray
    rivals: np.ndarray
    rival_pos: np.ndarray
    rival_vel: np.ndarray
    seen: np.ndarray
    pressure: float
    nearest_rival: int

    def rival_reach(self, points: np.ndarray, only_seen: bool = True, reach: float = 0.0) -> np.ndarray:
        t = self.state.traits
        r = self.rivals
        times = time_to_reach(
            self.rival_pos,
            self.rival_vel,
            points,
            t["top_speed"][r],
            t["acceleration"][r],
            t["reaction_time"][r],
            reach,
        )
        return np.where(self.seen[:, None] | (not only_seen), times, np.inf)

    def mate_reach(self, index: int, point: np.ndarray) -> float:
        t = self.state.traits
        slot = self.mates[index : index + 1]
        times = time_to_reach(
            self.mate_pos[index : index + 1],
            self.mate_vel[index : index + 1],
            point[None, :],
            t["top_speed"][slot],
            t["acceleration"][slot],
            t["reaction_time"][slot],
        )
        return float(times[0, 0])


def build_view(state: MatchState, carrier: int) -> CarrierView:
    team = 0 if carrier < 11 else 1
    sign = attack_sign(team, state.period)
    pos = to_attack_frame(state.pos[carrier], sign)
    velocity = state.vel[carrier] * sign
    speed = float(np.linalg.norm(velocity))
    facing = velocity / speed if speed > 1.0 else np.array([1.0, 0.0])
    mates = np.array([s for s in team_slots(team) if state.active[s] and s != carrier])
    rivals = np.array([s for s in team_slots(1 - team) if state.active[s]])
    rival_pos = to_attack_frame(state.pos[rivals], sign)
    offsets = rival_pos - pos
    distances = np.linalg.norm(offsets, axis=1)
    in_front = offsets @ facing > -0.3 * distances
    scan = state.traits["scan_radius"][carrier]
    seen = (distances < PERIPHERAL_RADIUS) | (in_front & (distances < 1.5 * scan))
    nearest = int(np.argmin(distances))
    return CarrierView(
        state,
        carrier,
        team,
        pos,
        facing,
        mates,
        to_attack_frame(state.pos[mates], sign),
        state.vel[mates] * sign,
        rivals,
        rival_pos,
        state.vel[rivals] * sign,
        seen,
        float(np.clip((4.5 - distances[nearest]) / 4.5, 0, 1)),
        nearest,
    )


def loss_if_lost(points: np.ndarray, risk: float) -> np.ndarray:
    """Cost of giving the ball away at `points`: the opponent's threat from there."""
    mirrored = np.array([PITCH_LENGTH, 2 * CENTRE_Y]) - np.atleast_2d(points)
    return (1.0 + 0.8 * (1.0 - risk)) * threat(mirrored[:, 0], mirrored[:, 1])
