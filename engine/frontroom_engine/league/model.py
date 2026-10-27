"""SynthLeague data model: clubs, players, latent traits and team styles.

Player skill is planted as physical and perceptual primitives (how fast, how far they scan, how
cleanly they strike a pass) rather than as "good at passing" scores. The analytics that run on the
output have to recover skill from behaviour, which is the point of the benchmark.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from frontroom_engine.league.formations import FORMATIONS


class Role(StrEnum):
    GK = "GK"
    RB = "RB"
    CB = "CB"
    LB = "LB"
    DM = "DM"
    CM = "CM"
    AM = "AM"
    RW = "RW"
    LW = "LW"
    ST = "ST"


@dataclass(frozen=True)
class Traits:
    """Latent per-player primitives. Units are physical where a unit exists."""

    top_speed: float
    """Maximum running speed in m/s."""
    acceleration: float
    """Maximum acceleration in m/s^2."""
    reaction_time: float
    """Seconds between a change on the pitch and the player starting to respond."""
    scan_radius: float
    """Metres within which the player reliably perceives teammates when choosing an option."""
    release_time: float
    """Seconds from controlling the ball to being ready to play it."""
    pass_noise: float
    """Standard deviation of pass direction error, in radians."""
    first_touch: float
    """0..1; probability scale for controlling a ball cleanly."""
    finishing: float
    """Standard deviation of shot placement at 11 m, in metres."""
    tackling: float
    dribbling: float
    aerial: float
    stamina: float
    discipline: float
    concentration: float
    """0..1; low values mean more frequent marking lapses."""
    goalkeeping: float
    """0..1; reach and handling. Only meaningful for goalkeepers."""


@dataclass(frozen=True)
class Player:
    id: str
    first_name: str
    last_name: str
    number: int
    role: Role
    traits: Traits

    @property
    def display_name(self) -> str:
        return f"{self.first_name[0]}. {self.last_name}"


@dataclass(frozen=True)
class TeamStyle:
    """Tactical identity in [0, 1] per axis; the simulator reads these as utility and shape weights."""

    directness: float
    tempo: float
    width: float
    line_height: float
    press: float
    risk: float
    formation: str

    def as_dict(self) -> dict[str, float | str]:
        return {
            "directness": self.directness,
            "tempo": self.tempo,
            "width": self.width,
            "lineHeight": self.line_height,
            "press": self.press,
            "risk": self.risk,
            "formation": self.formation,
        }


@dataclass(frozen=True)
class Club:
    id: str
    name: str
    short: str
    primary_colour: str
    secondary_colour: str
    style: TeamStyle
    squad: tuple[Player, ...]
    strength: float = field(default=0.0)
    """Club quality offset in roughly [-1, 1]; shifts every trait draw."""

    def starting_eleven(self) -> tuple[Player, ...]:
        """The first squad player of each role fills the formation slots, in slot order."""
        remaining = list(self.squad)
        eleven: list[Player] = []
        for slot in FORMATIONS[self.style.formation]:
            player = next(p for p in remaining if p.role == slot.role)
            remaining.remove(player)
            eleven.append(player)
        return tuple(eleven)

    def bench(self) -> tuple[Player, ...]:
        starters = {p.id for p in self.starting_eleven()}
        return tuple(p for p in self.squad if p.id not in starters)

    def player(self, player_id: str) -> Player:
        return next(p for p in self.squad if p.id == player_id)

    def by_number(self, number: int) -> Player:
        return next(p for p in self.squad if p.number == number)


@dataclass(frozen=True)
class League:
    name: str
    season: str
    seed: int
    clubs: tuple[Club, ...]

    def club(self, short: str) -> Club:
        return next(c for c in self.clubs if c.short == short.upper())
