"""SynthLeague: a fictional 20-club league with seeded squads, latent traits and team styles."""

from frontroom_engine.league.build import DEFAULT_LEAGUE_SEED, build_league
from frontroom_engine.league.model import Club, League, Player, Role, TeamStyle, Traits

__all__ = ["DEFAULT_LEAGUE_SEED", "Club", "League", "Player", "Role", "TeamStyle", "Traits", "build_league"]
