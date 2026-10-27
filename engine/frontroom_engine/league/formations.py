"""Formation templates.

Each slot has a depth offset from the team's block centre and a lateral position, both in the
team's attacking frame (attacking towards x = 105, so low y is the right flank). The simulator
stretches and slides these anchors with the ball and the phase of play.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    role: str
    depth: float
    lateral: float


def _slots(*rows: tuple[str, float, float]) -> tuple[Slot, ...]:
    return tuple(Slot(role, depth, lateral) for role, depth, lateral in rows)


_BACK_FOUR = (
    ("GK", -40.0, 34.0),
    ("RB", -11.0, 8.0),
    ("CB", -15.0, 25.0),
    ("CB", -15.0, 43.0),
    ("LB", -11.0, 60.0),
)

FORMATIONS: dict[str, tuple[Slot, ...]] = {
    "4-3-3": _slots(
        *_BACK_FOUR,
        ("DM", -6.0, 34.0),
        ("CM", 1.0, 46.0),
        ("CM", 1.0, 22.0),
        ("RW", 12.0, 7.0),
        ("ST", 15.0, 34.0),
        ("LW", 12.0, 61.0),
    ),
    "4-2-3-1": _slots(
        *_BACK_FOUR,
        ("DM", -5.0, 27.0),
        ("CM", -5.0, 41.0),
        ("AM", 6.0, 34.0),
        ("RW", 9.0, 9.0),
        ("ST", 15.0, 34.0),
        ("LW", 9.0, 59.0),
    ),
    "4-4-2": _slots(
        *_BACK_FOUR,
        ("CM", -3.0, 27.0),
        ("DM", -3.0, 41.0),
        ("RW", 1.0, 8.0),
        ("LW", 1.0, 60.0),
        ("ST", 13.0, 29.0),
        ("ST", 13.0, 39.0),
    ),
}
