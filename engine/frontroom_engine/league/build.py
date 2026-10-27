"""Seeded construction of SynthLeague.

Every club gets its own child seed, so adding a club or changing one club's style never reshuffles
the others. The two demo clubs have fixed styles and a few hand-set traits for their featured
players; everything else is drawn.
"""

import re

import numpy as np

from frontroom_engine.league.formations import FORMATIONS
from frontroom_engine.league.model import Club, League, Player, Role, TeamStyle, Traits
from frontroom_engine.league.names import CLUBS, FEATURED_PLAYERS, GIVEN_NAMES, SURNAMES

DEFAULT_LEAGUE_SEED = 2026

SQUAD_TEMPLATE: tuple[tuple[Role, int], ...] = (
    (Role.GK, 3),
    (Role.RB, 2),
    (Role.CB, 4),
    (Role.LB, 2),
    (Role.DM, 2),
    (Role.CM, 3),
    (Role.AM, 1),
    (Role.RW, 2),
    (Role.LW, 2),
    (Role.ST, 2),
)
STARTER_NUMBERS: dict[Role, tuple[int, ...]] = {
    Role.GK: (1,),
    Role.RB: (2,),
    Role.LB: (3,),
    Role.CB: (4, 5),
    Role.DM: (6,),
    Role.RW: (7,),
    Role.CM: (8,),
    Role.ST: (9,),
    Role.AM: (10,),
    Role.LW: (11,),
}

TRAIT_NAMES = (
    "top_speed",
    "acceleration",
    "reaction_time",
    "scan_radius",
    "release_time",
    "pass_noise",
    "first_touch",
    "finishing",
    "tackling",
    "dribbling",
    "aerial",
    "stamina",
    "discipline",
    "concentration",
    "goalkeeping",
)
_ROLE_MEANS: dict[str, tuple[float, ...]] = {
    "GK": (7.8, 3.2, 0.24, 25, 0.90, 0.075, 0.55, 1.8, 0.2, 0.20, 0.80, 0.60, 0.85, 0.75, 0.75),
    "CB": (8.4, 3.3, 0.26, 24, 0.75, 0.065, 0.60, 1.5, 0.7, 0.35, 0.75, 0.65, 0.65, 0.65, 0.10),
    "FB": (8.9, 3.6, 0.25, 26, 0.65, 0.060, 0.65, 1.35, 0.6, 0.55, 0.50, 0.80, 0.70, 0.60, 0.10),
    "DM": (8.4, 3.4, 0.24, 30, 0.55, 0.050, 0.72, 1.3, 0.68, 0.50, 0.60, 0.80, 0.60, 0.70, 0.10),
    "CM": (8.5, 3.5, 0.24, 30, 0.55, 0.050, 0.72, 1.2, 0.55, 0.60, 0.50, 0.80, 0.70, 0.65, 0.10),
    "AM": (8.6, 3.6, 0.23, 32, 0.50, 0.050, 0.78, 1.0, 0.35, 0.75, 0.40, 0.70, 0.75, 0.55, 0.10),
    "W": (9.1, 3.8, 0.23, 27, 0.55, 0.060, 0.72, 1.0, 0.30, 0.80, 0.35, 0.75, 0.75, 0.55, 0.10),
    "ST": (8.9, 3.7, 0.23, 24, 0.55, 0.065, 0.72, 0.8, 0.30, 0.65, 0.70, 0.70, 0.70, 0.55, 0.10),
}
# (sd, change per unit of quality, lower bound, upper bound); negative slopes mean "lower is better".
_TRAIT_SPREAD: tuple[tuple[float, float, float, float], ...] = (
    (0.25, 0.15, 8.0, 9.5),
    (0.2, 0.15, 3.0, 4.0),
    (0.02, -0.015, 0.18, 0.32),
    (4.0, 3.0, 12, 45),
    (0.08, -0.08, 0.3, 1.1),
    (0.008, -0.01, 0.025, 0.1),
    (0.07, 0.06, 0.3, 0.95),
    (0.15, -0.15, 0.5, 2.2),
    (0.08, 0.05, 0.05, 0.95),
    (0.08, 0.06, 0.05, 0.95),
    (0.08, 0.04, 0.05, 0.95),
    (0.08, 0.03, 0.3, 0.98),
    (0.08, 0.0, 0.3, 0.98),
    (0.07, 0.05, 0.3, 0.98),
    (0.06, 0.06, 0.05, 0.95),
)
_GK_SPEED_FLOOR = 7.0

DEMO_STYLES: dict[str, tuple[TeamStyle, float]] = {
    "KES": (TeamStyle(0.45, 0.65, 0.5, 0.7, 0.8, 0.55, "4-2-3-1"), 0.3),
    "ASH": (TeamStyle(0.25, 0.45, 0.6, 0.65, 0.45, 0.5, "4-3-3"), 0.15),
}
FEATURED_TRAITS: dict[tuple[str, int], dict[str, float]] = {
    ("KES", 6): {"tackling": 0.88, "reaction_time": 0.2, "stamina": 0.92, "concentration": 0.85},
    ("KES", 9): {"finishing": 0.65, "top_speed": 9.3, "acceleration": 3.9},
    ("KES", 10): {"scan_radius": 40.0, "pass_noise": 0.032, "first_touch": 0.88},
    ("ASH", 4): {"release_time": 0.85, "first_touch": 0.55, "dribbling": 0.3},
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _profile_key(role: Role) -> str:
    return {Role.RB: "FB", Role.LB: "FB", Role.RW: "W", Role.LW: "W"}.get(role, role.value)


def draw_traits(rng: np.random.Generator, role: Role, quality: float) -> Traits:
    means = _ROLE_MEANS[_profile_key(role)]
    values = {}
    for name, mean, (sd, slope, low, high) in zip(TRAIT_NAMES, means, _TRAIT_SPREAD, strict=True):
        if role == Role.GK and name == "top_speed":
            low = _GK_SPEED_FLOOR
        values[name] = float(np.clip(mean + slope * quality + sd * rng.standard_normal(), low, high))
    return Traits(**values)


def _style(rng: np.random.Generator) -> TeamStyle:
    axes = rng.beta(2.2, 2.2, size=6)
    formation = list(FORMATIONS)[int(rng.integers(len(FORMATIONS)))]
    return TeamStyle(*(round(float(a), 3) for a in axes), formation=formation)


def _starter_numbers(featured: dict[int, tuple[str, str, str]]) -> dict[Role, list[int]]:
    """Shirt numbers of each role's starters, with featured players' numbers moved to their roles."""
    numbers = {role: list(values) for role, values in STARTER_NUMBERS.items()}
    for number, (_, _, role) in featured.items():
        for values in numbers.values():
            if number in values:
                values.remove(number)
        numbers[Role(role)].insert(0, number)
    return numbers


def _squad(rng: np.random.Generator, short: str, strength: float) -> tuple[Player, ...]:
    featured = FEATURED_PLAYERS.get(short, {})
    used_names = {last for _, last, _ in featured.values()}
    bench_numbers = iter(rng.permutation(np.arange(12, 40))[:23])
    starters = _starter_numbers(featured)
    players: list[Player] = []
    for role, count in SQUAD_TEMPLATE:
        starter_numbers = starters[role]
        for index in range(count):
            number = starter_numbers[index] if index < len(starter_numbers) else int(next(bench_numbers))
            if number in featured:
                first, last, _ = featured[number]
            else:
                first = str(rng.choice(GIVEN_NAMES))
                last = str(rng.choice([s for s in SURNAMES if s not in used_names]))
                used_names.add(last)
            quality = (
                strength + (0.25 if index < len(starter_numbers) else -0.1) + 0.3 * rng.standard_normal()
            )
            traits = draw_traits(rng, role, quality)
            overrides = FEATURED_TRAITS.get((short, number))
            if overrides:
                traits = Traits(**{**traits.__dict__, **overrides})
            player_id = f"{short.lower()}-{number:02d}-{_slug(last)}"
            players.append(Player(player_id, first, last, number, role, traits))
    return tuple(players)


def build_league(seed: int = DEFAULT_LEAGUE_SEED) -> League:
    """Build all 20 clubs. The same seed always yields the same league."""
    root = np.random.SeedSequence(seed)
    clubs: list[Club] = []
    for (name, short, primary, secondary), child in zip(CLUBS, root.spawn(len(CLUBS)), strict=True):
        rng = np.random.default_rng(child)
        if short in DEMO_STYLES:
            style, strength = DEMO_STYLES[short]
        else:
            style, strength = _style(rng), float(rng.uniform(-0.8, 0.8))
        squad = _squad(rng, short, strength)
        clubs.append(Club(_slug(name), name, short, primary, secondary, style, squad, strength))
    return League("SynthLeague", "2026-27", seed, tuple(clubs))
