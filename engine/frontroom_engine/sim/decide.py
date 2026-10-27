"""Choosing among options: a softmax policy sampled with keyed Gumbel noise.

Gumbel-max with noise from the tape gives the same choice as sampling from the softmax, but the
draw for option i at (player, tick) is fixed. A counterfactual that changes nothing upstream
therefore makes the same choice, which keeps paired replays paired.
"""

import numpy as np

from frontroom_engine.sim.geometry import attack_sign, to_attack_frame
from frontroom_engine.sim.noise import NoiseTape
from frontroom_engine.sim.options import Option, enumerate_options
from frontroom_engine.sim.records import Decision, OptionRecord
from frontroom_engine.sim.setup import HOME_EDGE, MatchSetup
from frontroom_engine.sim.state import MatchState

TEMPERATURE = 0.035

RESTART_KINDS: dict[str, tuple[str, ...]] = {
    "throw_in": ("pass", "long"),
    "corner": ("cross", "pass"),
    "goal_kick": ("pass", "long"),
    "free_kick": ("pass", "long", "cross", "shot"),
    "penalty": ("shot",),
    "kick_off": ("pass",),
    "keeper": ("pass", "long"),
}


THROW_RANGE = 30.0


def _allowed(options: list[Option], restart: str | None, carrier: np.ndarray) -> list[Option]:
    """Restrict a set piece to the options that restart allows, falling back to any pass."""
    if restart is None:
        return options
    kinds = RESTART_KINDS[restart]
    allowed = [o for o in options if o.kind in kinds]
    if restart == "throw_in":
        allowed = [o for o in allowed if np.linalg.norm(o.end - carrier) < THROW_RANGE]
    if restart == "kick_off":
        allowed = [o for o in allowed if o.end[0] < carrier[0]]
    return allowed or [o for o in options if o.kind in ("pass", "long")] or options


def decide(
    state: MatchState,
    setup: MatchSetup,
    tape: NoiseTape,
    carrier: int,
    restart: str | None = None,
    forced: int | None = None,
) -> tuple[Option, int]:
    """Pick an option for `carrier`, record the decision as latent truth, and return it with its action id."""
    team = 0 if carrier < 11 else 1
    sign = attack_sign(team, state.period)
    options = _allowed(
        enumerate_options(state, setup, carrier), restart, to_attack_frame(state.pos[carrier], sign)
    )
    utilities = np.array([option.utility for option in options])
    temperature = TEMPERATURE * (1.0 - HOME_EDGE if team == 0 else 1.0)
    scaled = utilities / temperature
    if forced is not None:
        chosen = forced
    else:
        chosen = int(np.argmax(scaled + tape.gumbel("decide", state.tick, carrier, len(options))))
    weights = np.exp(scaled - scaled.max())
    probabilities = weights / weights.sum()
    action_id = state.new_action_id()
    records = tuple(
        OptionRecord(
            kind=option.kind,
            target_player=state.player_id(option.target_slot) if option.target_slot >= 0 else None,
            end=tuple(np.round(to_attack_frame(option.end, sign), 2).tolist()),
            utility=round(option.utility, 4),
            perceived_success=round(option.success, 4),
        )
        for option in options
    )
    state.decisions.append(
        Decision(
            action_id,
            state.tick,
            state.player_id(carrier),
            records,
            tuple(np.round(probabilities, 4).tolist()),
            chosen,
        )
    )
    return options[chosen], action_id
