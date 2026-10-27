"""Steer a match towards a storyline by choosing among physically simulated futures.

Method. The simulator never gets told what should happen. From a checkpoint the match is
re-simulated several times over the next few seconds, each time with a different branch of
the keyed noise tape (`NoiseTape.branched`). Every candidate obeys the same physics and
decision model; the steering only picks which future to keep, greedily by a progress score,
and stops as soon as the beat has happened. If a beat cannot be reached before its deadline
the search restarts from the beat's checkpoint with fresh branches, and if a later beat keeps
failing the search backtracks into the earlier one.

Realism cost. Selection is conditioning: the kept match is a draw from the engine *given* the
storyline, so the steered minutes are less typical than unsteered ones. `SteeringReport`
records how much was simulated per minute kept and an upper bound on the information the
selection injected (log of the number of candidates per decision, in nats). Outside the
steered windows the match runs untouched, and the scorecard can be run on steered matches too.

Reproducibility. The result is fully described by the match seed plus the list of
(tick, salt) branch points, so a found storyline is saved as a small recipe and replayed
exactly without searching again.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from frontroom_engine.sim.core import Simulator
from frontroom_engine.sim.match import run, run_to_minute
from frontroom_engine.sim.noise import NoiseTape
from frontroom_engine.sim.records import Action, DetailValue, StoryBeat
from frontroom_engine.sim.state import MatchState

SEGMENT_TICKS = 50
CANDIDATES = 12
MAX_RESTARTS = 40


class StoryNotFound(RuntimeError):
    pass


@dataclass(frozen=True)
class Beat:
    """One storyline event: where to start looking, until when, how close we are, and the test."""

    name: str
    start: Callable[[Simulator], None]
    deadline: Callable[[Simulator], int]
    progress: Callable[[Simulator], float]
    found: Callable[[Sequence[Action], Sequence[StoryBeat]], dict[str, DetailValue] | None]
    """Look through the actions since the beat's checkpoint (and the beats already found) for the
    beat. It reads only the action log, so a replayed match can be checked without searching."""
    viable: Callable[[Simulator, dict[str, DetailValue]], bool] = lambda sim, detail: True
    """Search-time check that a found beat still leaves the next beat reachable."""


@dataclass
class SteeringReport:
    segments_kept: int = 0
    ticks_simulated: int = 0
    restarts: int = 0
    found: list[StoryBeat] = field(default_factory=list)

    @property
    def conditioning_nats(self) -> float:
        """Upper bound on the information injected by choosing among candidates."""
        return self.segments_kept * math.log(CANDIDATES)

    def as_dict(self) -> dict[str, float | int]:
        return {
            "segmentSeconds": SEGMENT_TICKS / 10,
            "candidatesPerSegment": CANDIDATES,
            "segmentsKept": self.segments_kept,
            "restarts": self.restarts,
            "simulatedSeconds": self.ticks_simulated / 10,
            "conditioningNats": round(self.conditioning_nats, 2),
        }


def _salt(beat: int, restart: int, segment: int, candidate: int) -> int:
    return 1 + ((beat * MAX_RESTARTS + restart) * 10_000 + segment) * CANDIDATES + candidate


def _restore(sim: Simulator, state: MatchState, tape: NoiseTape) -> None:
    sim.state = state.clone()
    sim.tape = tape
    sim.finished = False


def _attempt(sim: Simulator, beat: Beat, index: int, restart: int, report: SteeringReport) -> bool:
    """Greedy segment search for one beat from the current state; True if the beat happened."""
    first_action = len(sim.state.actions)
    deadline = beat.deadline(sim)
    segment = 0
    while sim.state.tick < deadline and not sim.finished:
        base_state, base_tape = sim.state.clone(), sim.tape
        best_score, best_tape = -math.inf, base_tape
        for candidate in range(CANDIDATES):
            tape = base_tape.branched(base_state.tick, _salt(index, restart, segment, candidate))
            _restore(sim, base_state, tape)
            run(sim, until_tick=base_state.tick + SEGMENT_TICKS)
            report.ticks_simulated += sim.state.tick - base_state.tick
            detail = beat.found(sim.state.actions[first_action:], sim.state.beats)
            if detail is not None and beat.viable(sim, detail):
                report.segments_kept += segment + 1
                beat_record = StoryBeat(beat.name, beat_tick(sim.state.actions, detail), detail)
                sim.state.beats.append(beat_record)
                report.found.append(beat_record)
                return True
            score = beat.progress(sim)
            if score > best_score:
                best_score, best_tape = score, tape
        _restore(sim, base_state, best_tape)
        run(sim, until_tick=base_state.tick + SEGMENT_TICKS)
        segment += 1
    return False


def _search(sim: Simulator, beats: list[Beat], index: int, report: SteeringReport) -> bool:
    if index == len(beats):
        return True
    beat = beats[index]
    beat.start(sim)
    origin_state, origin_tape = sim.state.clone(), sim.tape
    kept_segments, found_count = report.segments_kept, len(report.found)
    for restart in range(MAX_RESTARTS):
        _restore(sim, origin_state, origin_tape)
        report.segments_kept = kept_segments
        del report.found[found_count:]
        if _attempt(sim, beat, index, restart, report) and _search(sim, beats, index + 1, report):
            return True
        report.restarts += 1
    _restore(sim, origin_state, origin_tape)
    return False


def steer(sim: Simulator, beats: list[Beat]) -> SteeringReport:
    """Run `sim` through every beat in order, or raise `StoryNotFound`."""
    report = SteeringReport()
    if not _search(sim, beats, 0, report):
        raise StoryNotFound(" -> ".join(beat.name for beat in beats))
    return report


def beat_tick(actions: Sequence[Action], detail: Mapping[str, DetailValue]) -> int:
    """When a beat happened: the earliest of the actions its detail points at."""
    referenced = {int(value) for key, value in detail.items() if key.endswith("Action")}
    return min(action.tick for action in actions if action.id in referenced)


def action_minute(action: Action) -> float:
    return (action.period - 1) * 45 + action.clock_ms / 60000


def wait_until(minute: float) -> Callable[[Simulator], None]:
    return lambda sim: run_to_minute(sim, minute)


def at_minute(minute: float) -> Callable[[Simulator], int]:
    """Deadline at a broadcast minute of the half the simulation is currently in."""

    def deadline(sim: Simulator) -> int:
        period_offset = 45 if sim.state.period == 2 else 0
        return sim.state.period_start_tick + round((minute - period_offset) * 600)

    return deadline


def within(seconds: float) -> Callable[[Simulator], int]:
    return lambda sim: sim.state.tick + round(seconds * 10)
