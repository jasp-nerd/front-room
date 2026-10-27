"""Static description of one fixture: who plays, in what shape, with which seed."""

from dataclasses import dataclass

import numpy as np

from frontroom_engine.league.formations import FORMATIONS
from frontroom_engine.league.model import Club, League, TeamStyle

HOME_EDGE = 0.10
"""Relative improvement in execution noise and decision sharpness for the home side."""


@dataclass(frozen=True)
class TeamSetup:
    club: Club
    style: TeamStyle
    depth: np.ndarray
    lateral: np.ndarray
    roles: tuple[str, ...]

    @classmethod
    def for_club(cls, club: Club) -> "TeamSetup":
        slots = FORMATIONS[club.style.formation]
        return cls(
            club=club,
            style=club.style,
            depth=np.array([s.depth for s in slots]),
            lateral=np.array([s.lateral for s in slots]),
            roles=tuple(s.role for s in slots),
        )


@dataclass(frozen=True)
class MatchSetup:
    match_id: str
    seed: int
    league: League
    home: TeamSetup
    away: TeamSetup
    kept_on: frozenset[str] = frozenset()
    """Players never substituted. A storyline uses this to keep its cast on the pitch."""

    def team(self, team: int) -> TeamSetup:
        return self.home if team == 0 else self.away


def make_setup(
    league: League, home_short: str, away_short: str, seed: int, kept_on: frozenset[str] = frozenset()
) -> MatchSetup:
    home, away = league.club(home_short), league.club(away_short)
    match_id = f"sl-{home.short.lower()}-{away.short.lower()}-{seed}"
    return MatchSetup(match_id, seed, league, TeamSetup.for_club(home), TeamSetup.for_club(away), kept_on)
