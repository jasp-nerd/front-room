"""Preallocated 10 Hz recording of positions, speeds, ball and roster.

Rows are indexed by tick. A scenario branch that rewinds to a checkpoint simply overwrites the
rows after it, so checkpoints never need to copy the recording.
"""

from dataclasses import dataclass, field

import numpy as np

from frontroom_engine.sim.state import SLOTS, MatchState

MAX_TICKS = 2 * 56 * 600


@dataclass
class Recording:
    period: np.ndarray = field(default_factory=lambda: np.zeros(MAX_TICKS, dtype=np.int8))
    clock_ms: np.ndarray = field(default_factory=lambda: np.zeros(MAX_TICKS, dtype=np.int64))
    pos: np.ndarray = field(default_factory=lambda: np.zeros((MAX_TICKS, SLOTS, 2), dtype=np.float32))
    speed: np.ndarray = field(default_factory=lambda: np.zeros((MAX_TICKS, SLOTS), dtype=np.float32))
    ball: np.ndarray = field(default_factory=lambda: np.zeros((MAX_TICKS, 3), dtype=np.float32))
    alive: np.ndarray = field(default_factory=lambda: np.zeros(MAX_TICKS, dtype=bool))
    roster: np.ndarray = field(default_factory=lambda: np.full((MAX_TICKS, SLOTS), -1, dtype=np.int16))
    player_ids: list[str] = field(default_factory=list)
    length: int = 0
    _index: dict[str, int] = field(default_factory=dict, repr=False)

    def _roster_index(self, player_id: str) -> int:
        index = self._index.get(player_id)
        if index is None:
            index = self._index[player_id] = len(self.player_ids)
            self.player_ids.append(player_id)
        return index

    def capture(self, state: MatchState) -> None:
        row = state.tick
        self.period[row] = state.period
        self.clock_ms[row] = (state.tick - state.period_start_tick) * 100
        self.pos[row] = state.pos
        self.speed[row] = np.linalg.norm(state.vel, axis=1)
        self.ball[row] = state.ball_pos
        self.alive[row] = state.phase == "play"
        self.roster[row] = [
            self._roster_index(player.id) if player is not None and state.active[slot] else -1
            for slot, player in enumerate(state.players)
        ]
        self.length = row + 1
