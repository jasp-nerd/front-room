"""The simulator object shared by the phase modules (play, flight, restarts, referee)."""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from frontroom_engine.sim.geometry import attack_sign, to_attack_frame
from frontroom_engine.sim.noise import NoiseTape
from frontroom_engine.sim.recorder import Recording
from frontroom_engine.sim.records import Action, DetailValue, Point
from frontroom_engine.sim.setup import MatchSetup
from frontroom_engine.sim.state import MatchState, team_slots

TICKS_PER_SECOND = 10
TICKS_PER_MINUTE = 600


def point(xy: np.ndarray) -> Point:
    return (round(float(xy[0]), 2), round(float(xy[1]), 2))


@dataclass
class Simulator:
    setup: MatchSetup
    tape: NoiseTape
    state: MatchState
    recording: Recording
    finished: bool = False
    forced_choice: tuple[int, int, int] | None = None
    """(tick, slot, option index): make that decision come out as that option. Used by counterfactuals."""
    withheld: tuple[int, int, int] | None = None
    """(slot, first tick, last tick): that player cannot tackle or control the ball in the window."""

    def forced_option(self, slot: int) -> int | None:
        forced = self.forced_choice
        if forced is not None and forced[0] == self.state.tick and forced[1] == slot:
            return forced[2]
        return None

    def is_withheld(self, slot: int) -> bool:
        return (
            self.withheld is not None
            and self.withheld[0] == slot
            and self.withheld[1] <= self.state.tick <= self.withheld[2]
        )

    @property
    def clock_ms(self) -> int:
        return (self.state.tick - self.state.period_start_tick) * 100

    @property
    def minute(self) -> float:
        """Match minute as broadcast clocks show it (the second half starts at 45)."""
        return (self.state.period - 1) * 45 + self.clock_ms / 60000

    def sign(self, team: int) -> int:
        return attack_sign(team, self.state.period)

    def relative(self, xy: np.ndarray, team: int) -> np.ndarray:
        return to_attack_frame(xy, self.sign(team))

    def active_slots(self, team: int) -> list[int]:
        return [slot for slot in team_slots(team) if self.state.active[slot]]

    def keeper(self, team: int) -> int:
        return 11 * team

    def act(
        self,
        kind: str,
        slot: int,
        start: np.ndarray | Point,
        *,
        end: np.ndarray | Point | None = None,
        result: str = "none",
        body_part: str = "foot",
        action_id: int | None = None,
        tick: int | None = None,
        detail: Mapping[str, DetailValue] | None = None,
        latent: Mapping[str, DetailValue] | None = None,
    ) -> Action:
        """Append an on-ball action. `tick` defaults to now; passes are logged when they resolve."""
        s = self.state
        at = s.tick if tick is None else tick
        action = Action(
            id=s.new_action_id() if action_id is None else action_id,
            tick=at,
            period=s.period,
            clock_ms=(at - s.period_start_tick) * 100,
            kind=kind,
            slot=slot,
            player_id=s.player_id(slot),
            team=0 if slot < 11 else 1,
            start=point(np.asarray(start)),
            end=None if end is None else point(np.asarray(end)),
            result=result,
            body_part=body_part,
            possession=s.possession_id,
            end_tick=s.tick,
            detail=dict(detail or {}),
            latent=dict(latent or {}),
        )
        s.actions.append(action)
        return action

    def change_possession(self, team: int) -> None:
        s = self.state
        if s.possession_team != team:
            s.possession_team = team
            s.possession_id += 1
            s.unflagged_offside = None

    def log_carry(self, slot: int) -> None:
        """Log the carry since the last touch as a SPADL-style dribble if it covered real ground."""
        s = self.state
        start = np.array(s.carry_start)
        if np.linalg.norm(s.pos[slot] - start) >= 3.0:
            self.act("dribble", slot, start, end=s.pos[slot], result="success", tick=s.carry_start_tick)
        s.carry_start = point(s.pos[slot])
        s.carry_start_tick = s.tick
