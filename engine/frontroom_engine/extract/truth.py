"""Latent truth for one match: everything the simulator knows that the feed does not show.

This is what makes the synthetic data gradeable: the options each player weighed and the
probabilities of each, the physical chance every shot really had, every offside margin and
whether it was flagged, the planted traits and styles, and the storyline beats if steered.
Feed event ids link each record back to `events.jsonl`.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from frontroom_engine.extract.events import Feed
from frontroom_engine.sim.match import MatchResult
from frontroom_engine.sim.recorder import Recording
from frontroom_engine.sim.records import Action, Decision


def _clock(recording: Recording, tick: int) -> dict[str, int]:
    row = min(tick, recording.length - 1)
    return {"period": int(recording.period[row]), "clockMs": int(recording.clock_ms[row])}


def _decision(decision: Decision, event_ids: Mapping[int, str], recording: Recording) -> dict[str, Any]:
    return {
        "eventId": event_ids.get(decision.action_id),
        **_clock(recording, decision.tick),
        "playerId": decision.player_id,
        "chosen": decision.chosen,
        "options": [
            {
                "kind": option.kind,
                "target": option.target_player,
                "end": list(option.end),
                "utility": option.utility,
                "perceivedSuccess": option.perceived_success,
                "probability": probability,
            }
            for option, probability in zip(decision.options, decision.probabilities, strict=True)
        ],
    }


def _possessions(actions: list[Action], event_ids: Mapping[int, str]) -> list[dict[str, Any]]:
    """Each possession with how it started; origin analysis begins from these."""
    grouped: dict[int, list[Action]] = defaultdict(list)
    for action in actions:
        if action.id in event_ids:
            grouped[action.possession].append(action)
    possessions = []
    for possession, members in sorted(grouped.items()):
        members.sort(key=lambda a: (a.tick, a.id))
        on_ball = [a for a in members if a.kind != "press"]
        first = on_ball[0] if on_ball else members[0]
        possessions.append(
            {
                "possession": possession,
                "side": "home" if first.team == 0 else "away",
                "startEventId": event_ids[first.id],
                "startType": first.kind,
                "events": len(members),
                "goal": any(a.kind == "goal" and a.result == "success" for a in members),
            }
        )
    return possessions


def story_action_ids(detail: Mapping[str, Any]) -> list[int]:
    """Action ids a story beat points at (keys ending in `Action` or `Actions`)."""
    found: list[int] = []
    for key, value in detail.items():
        if key.endswith("Action"):
            found.append(int(value))
        elif key.endswith("Actions"):
            found.extend(int(part) for part in str(value).split(",") if part)
    return found


def _story_events(detail: Mapping[str, Any], ids: Mapping[int, str]) -> dict[str, Any]:
    events: dict[str, Any] = {}
    for key, value in detail.items():
        if key.endswith("Action"):
            events[key.removesuffix("Action") + "Event"] = ids.get(int(value))
        elif key.endswith("Actions"):
            events[key.removesuffix("Actions") + "Events"] = [
                ids.get(int(v)) for v in str(value).split(",") if v
            ]
    return events


def build_truth(result: MatchResult, feed: Feed, steering: Mapping[str, Any] | None = None) -> dict[str, Any]:
    state, setup, recording = result.state, result.setup, result.recording
    ids = feed.event_ids
    clubs = {"home": setup.home, "away": setup.away}
    return {
        "matchId": setup.match_id,
        "seed": setup.seed,
        "generator": "G_B: 10 Hz physical simulation",
        "teams": {
            side: {"clubId": team.club.id, "strength": team.club.strength, "style": team.style.as_dict()}
            for side, team in clubs.items()
        },
        "playerTraits": {
            player.id: {name: round(value, 4) for name, value in asdict(player.traits).items()}
            for team in clubs.values()
            for player in team.club.squad
        },
        "shots": [
            {
                "eventId": ids.get(shot.action_id),
                "xg": shot.xg,
                "onTargetProbability": shot.on_target_probability,
                "outcome": shot.outcome,
                "distance": shot.distance,
                "pressure": shot.pressure,
            }
            for shot in state.shots
        ],
        "offsides": [
            {
                "passEventId": ids.get(o.action_id),
                "receiver": o.receiver_id,
                "margin": o.margin,
                "flagged": o.flagged,
            }
            for o in state.offsides
        ],
        "possessions": _possessions(state.actions, ids),
        "decisions": [_decision(d, ids, recording) for d in state.decisions],
        "story": [
            {
                "beat": beat.name,
                **_clock(recording, beat.tick),
                "events": _story_events(beat.detail, ids),
                "detail": {
                    key: value
                    for key, value in beat.detail.items()
                    if not key.endswith(("Action", "Actions"))
                },
            }
            for beat in state.beats
        ],
        "steering": {"branches": [list(b) for b in result.branches], **(steering or {})},
    }
