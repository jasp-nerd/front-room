"""Tonight's players, as a fan can name them: the surname when it is unique, the short name when it isn't
(both clubs have a Petrov). Read from the demo match the server ships with."""

from __future__ import annotations

import json
from collections import Counter
from functools import cache
from pathlib import Path

METADATA = Path(__file__).parents[1] / "server" / "demo_match" / "metadata.json"


@cache
def players() -> dict[str, str]:
    """Label -> player id, for the starting players of both clubs."""
    if not METADATA.exists():
        return {}
    metadata = json.loads(METADATA.read_text())
    starters = [p for side in ("home", "away") for p in metadata[side]["squad"] if p["starting"]]
    surnames = Counter(p["shortName"].split(". ")[-1] for p in starters)
    labels = {}
    for p in starters:
        surname = p["shortName"].split(". ")[-1]
        labels[surname if surnames[surname] == 1 else p["shortName"]] = p["playerId"]
    return labels


def labels() -> list[str]:
    return list(players())
