"""A fan's viewing profile. It is built on their phone from what they say, and it never leaves the phone.

The room only ever receives the bids an agent places, never the profile behind them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ClubId = Literal["kestrel", "ashvale"]
Depth = Literal["analyst", "casual", "kid", "audio"]
Metric = Literal["distance", "top-speed", "shots-on-target", "pass-accuracy", "possession"]
"""The one number a fan can ask to keep in view, measured from the match's tracking and event feed."""


class FanProfile(BaseModel):
    club: ClubId | None = Field(description="The club the fan supports, if they said.")
    depth: Depth = Field(
        description="analyst: wants tactics and numbers. casual: the story, kept simple. "
        "kid: a young fan. audio: low vision or listening rather than watching."
    )
    language: str = Field(description="ISO 639-1 code of the language the fan wants on their phone.")
    needs: list[Literal["captions", "described-audio", "large-text", "no-flashing"]] = Field(
        default_factory=list, description="Access needs the fan mentioned for themselves or the room."
    )
    likes: list[str] = Field(
        default_factory=list, description="Short notes on what they enjoy, in English: 'pressing', 'goals'."
    )
    players: list[str] = Field(
        default_factory=list,
        description="Players the fan follows, by surname exactly as in the squad lists, e.g. 'Okafor'.",
    )
    metric: Metric | None = Field(
        default=None,
        description="The one number they want to keep an eye on, if they named one: distance covered, "
        "top speed, shots on target, pass accuracy or possession.",
    )


PROFILE_INSTRUCTIONS = """\
You set up a football fan's private viewing profile from what they tell you, in any language.
Only record what they actually said or clearly implied. If they don't name a club, leave club empty.
The clubs in this league are Kestrel FC (kestrel) and Ashvale Athletic (ashvale).
Only list players from the squads below, by surname as written there; leave players empty if they name none.
"""


def profile_instructions(squad: list[str]) -> str:
    """The instructions with tonight's squads, so the model can only follow players who exist."""
    return PROFILE_INSTRUCTIONS + "Squads: " + ", ".join(squad) + "\n"
