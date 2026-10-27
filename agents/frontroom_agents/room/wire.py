"""The Director's inputs and outputs as protocol JSON (packages/protocol/schema), and back again.

The room server sends decisions to the screens in this shape, and the A2A Director receives a round and
answers in it, so the conversion lives in one place.
"""

from __future__ import annotations

from typing import Any

from .director import Bid, Candidate, Constraint, Decision, RoomState, Scored, Weight


def decision_to_wire(decision: Decision, room_id: str, decision_id: str) -> dict[str, Any]:
    """The Decision in the shape of protocol/schema/decision.schema.json."""
    return {
        "roomId": room_id,
        "decisionId": decision_id,
        "pts": decision.pts,
        "weights": [
            {
                "agentId": w.agent_id,
                "weight": round(w.weight, 4),
                "secondsWithoutScreen": w.seconds_without_screen,
            }
            for w in decision.weights
        ],
        "candidates": [
            {
                "candidateId": c.candidate_id,
                "rawScore": c.raw_score,
                "fairScore": c.fair_score,
                **({"struckBy": str(c.struck_by)} if c.struck_by else {}),
                "won": c.won,
                "askedBy": list(c.asked_by),
            }
            for c in decision.candidates
        ],
        "deliveredPrivately": [
            {"agentId": agent, "candidateId": candidate}
            for agent, candidate in decision.delivered_privately.items()
        ],
        "decidedInMs": round(decision.decided_in_ms, 3),
    }


def decision_from_wire(wire: dict[str, Any]) -> Decision:
    winner = next((c["candidateId"] for c in wire["candidates"] if c["won"]), None)
    return Decision(
        pts=int(wire["pts"]),
        weights=[Weight(w["agentId"], w["weight"], w["secondsWithoutScreen"]) for w in wire["weights"]],
        candidates=[
            Scored(
                c["candidateId"],
                c["rawScore"],
                c["fairScore"],
                Constraint(c["struckBy"]) if c.get("struckBy") else None,
                c["won"],
                tuple(c.get("askedBy", ())),
            )
            for c in wire["candidates"]
        ],
        winner=winner,
        delivered_privately={d["agentId"]: d["candidateId"] for d in wire["deliveredPrivately"]},
        decided_in_ms=wire["decidedInMs"],
    )


def round_to_wire(
    candidates: list[Candidate], bids: list[Bid], state: RoomState, room_id: str
) -> dict[str, Any]:
    """One decision round as a personal agent's side sends it: overlays, bids and room facts. No profiles."""
    return {
        "roomId": room_id,
        "candidates": [{"id": c.id, "pts": c.pts, "partisan": c.partisan} for c in candidates],
        "bids": [{"agentId": b.agent_id, "candidateId": b.candidate_id, "utility": b.utility} for b in bids],
        "state": {
            "agentIds": state.agent_ids,
            "bothClubsPresent": state.both_clubs_present,
            "tvPts": state.tv_pts,
            "overlayOnAir": state.overlay_on_air,
            "lastOverlayEndPts": state.last_overlay_end_pts,
            "varCheck": state.var_check,
            "secondsWithoutScreen": state.seconds_without_screen,
        },
    }


def round_from_wire(wire: dict[str, Any]) -> tuple[list[Candidate], list[Bid], RoomState]:
    """The inverse of round_to_wire. A2A data parts carry every number as a float, so times are turned
    back into whole milliseconds."""
    state = wire["state"]
    last_end = state.get("lastOverlayEndPts")
    return (
        [Candidate(c["id"], int(c["pts"]), bool(c["partisan"])) for c in wire["candidates"]],
        [Bid(b["agentId"], b["candidateId"], float(b["utility"])) for b in wire["bids"]],
        RoomState(
            agent_ids=list(state["agentIds"]),
            both_clubs_present=bool(state["bothClubsPresent"]),
            tv_pts=int(state["tvPts"]),
            overlay_on_air=bool(state.get("overlayOnAir", False)),
            last_overlay_end_pts=int(last_end) if last_end is not None else None,
            var_check=bool(state.get("varCheck", False)),
            seconds_without_screen={k: float(v) for k, v in state.get("secondsWithoutScreen", {}).items()},
        ),
    )
