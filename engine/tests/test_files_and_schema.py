"""The written files validate against the shared protocol schemas and agree with each other."""

import json

import jsonschema
import numpy as np
import pyarrow.parquet as pq

from frontroom_engine.io import MatchFiles, read_events, read_tracking_frames


def test_every_event_validates_against_the_match_event_schema(
    match_files: MatchFiles, event_validator: jsonschema.Draft202012Validator
) -> None:
    events = read_events(match_files.events)
    assert len(events) > 1000
    for event in events:
        event_validator.validate(event)


def test_sampled_tracking_frames_validate_against_the_tracking_frame_schema(
    match_files: MatchFiles, frame_validator: jsonschema.Draft202012Validator
) -> None:
    match_id = json.loads(match_files.metadata.read_text())["matchId"]
    frames = list(read_tracking_frames(match_files.tracking, match_id, limit=2000))
    assert len(frames) == 2000
    for frame in frames[::50]:
        frame_validator.validate(frame)


def test_metadata_score_matches_the_goal_events(match_files: MatchFiles) -> None:
    metadata = json.loads(match_files.metadata.read_text())
    events = read_events(match_files.events)
    corrected = {e["amends"] for e in events if "amends" in e}
    goals = [e for e in events if e["type"] == "goal" and e["id"] not in corrected and "amends" not in e]
    scored = {"home": 0, "away": 0}
    for goal in goals:
        scoring_side = goal["detail"]["scoringSide"]
        scored[scoring_side] += 1
    assert scored == metadata["score"]


def test_events_are_ordered_and_inside_their_period(match_files: MatchFiles) -> None:
    metadata = json.loads(match_files.metadata.read_text())
    durations = {p["period"]: p["durationMs"] for p in metadata["periods"]}
    events = read_events(match_files.events)
    seqs = [e["seq"] for e in events if "amends" not in e]
    assert seqs == sorted(seqs) == list(range(len(seqs)))
    for event in events:
        assert event["clockMs"] <= durations[event["period"]] + 1000


def test_event_locations_agree_with_the_tracked_ball(match_files: MatchFiles) -> None:
    """Pass origins in the feed sit where the tracked ball was, up to the labelling noise."""
    table = pq.read_table(match_files.tracking, columns=["period", "clock_ms", "ball_x", "ball_y"])
    period = table["period"].to_numpy()
    clock = table["clock_ms"].to_numpy()
    ball = np.stack([table["ball_x"].to_numpy(), table["ball_y"].to_numpy()], axis=1)
    gaps = []
    for event in read_events(match_files.events):
        if event["type"] != "pass":
            continue
        frames = np.flatnonzero(period == event["period"])
        nearest = frames[np.argmin(np.abs(clock[frames] - event["clockMs"]))]
        gaps.append(np.hypot(ball[nearest, 0] - event["start"]["x"], ball[nearest, 1] - event["start"]["y"]))
    assert np.median(gaps) < 2.5
    assert np.percentile(gaps, 90) < 6.0


def test_truth_links_every_shot_and_decision_to_the_feed(match_files: MatchFiles) -> None:
    truth = json.loads(match_files.truth.read_text())
    event_ids = {e["id"] for e in read_events(match_files.events)}
    assert truth["shots"] and all(shot["eventId"] in event_ids for shot in truth["shots"])
    assert all(0.0 <= shot["xg"] <= 1.0 for shot in truth["shots"])
    for decision in truth["decisions"][:500]:
        probabilities = [option["probability"] for option in decision["options"]]
        assert abs(sum(probabilities) - 1.0) < 0.01
        assert 0 <= decision["chosen"] < len(decision["options"])
