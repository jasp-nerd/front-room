"""Described audio from Azure AI Speech: the fan who would rather listen hears the TV's story in their ear.

When a goal's cues go out, every phone whose fan listens (an audio-first profile, or one that needs described
audio) gets a link to that story spoken in their language. The audio is synthesised once per text and
language, in the background, so the cue goes out without waiting for it. The link carries the fan's phone
token, because the phone's cue is private and so is its audio.

Speech runs on the Foundry resource's key, in its region (FRONTROOM_FOUNDRY_KEY, FRONTROOM_SPEECH_REGION).
Without them the cues simply carry no audio, and the phone shows the words.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

import aiohttp

from ..personal.agent import PersonalAgent

VOICES = {"en": ("en-GB", "en-GB-SoniaNeural"), "es": ("es-ES", "es-ES-ElviraNeural")}
FORMAT = "audio-24khz-48kbitrate-mono-mp3"
MAX_CLIPS = 200
"""Clips kept in memory; a match night needs a handful per goal."""

Synthesiser = Callable[[str, str], Awaitable[bytes]]
"""(text, language) -> mp3 bytes."""


@dataclass(frozen=True)
class AzureSpeech:
    """Text to speech over the Speech REST endpoint, with a neural voice per language."""

    key: str
    region: str

    @classmethod
    def from_env(cls) -> AzureSpeech | None:
        key, region = os.environ.get("FRONTROOM_FOUNDRY_KEY"), os.environ.get("FRONTROOM_SPEECH_REGION")
        return cls(key, region) if key and region else None

    async def __call__(self, text: str, lang: str) -> bytes:
        locale, voice = VOICES.get(lang, VOICES["en"])
        ssml = (
            f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>{escape(text)}</voice></speak>"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": FORMAT,
        }
        url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session,
            session.post(url, data=ssml.encode(), headers=headers) as response,
        ):
            response.raise_for_status()
            return await response.read()


def listens(agent: PersonalAgent) -> bool:
    """Whether this fan wants the story spoken: they watch audio-first, or they need described audio."""
    return agent.profile.depth == "audio" or "described-audio" in agent.profile.needs


def clip_id(text: str, lang: str) -> str:
    return hashlib.sha256(f"{lang}\n{text}".encode()).hexdigest()[:20]


@dataclass
class Narrator:
    """Synthesises the clips the phones are told about, and hands each only to the fans it was made for."""

    synthesise: Synthesiser
    clips: OrderedDict[str, asyncio.Task[bytes]] = field(default_factory=OrderedDict)
    listeners: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    """(room, clip) -> the fans whose cue linked to it."""

    def prepare(self, room: str, fan: str, text: str, lang: str) -> str:
        clip = clip_id(text, lang)
        if clip not in self.clips:
            self.clips[clip] = asyncio.create_task(self.synthesise(text, lang))
            while len(self.clips) > MAX_CLIPS:
                self.clips.popitem(last=False)
        self.listeners.setdefault((room, clip), set()).add(fan)
        return clip

    def attach(self, room: str, agent: PersonalAgent, cue: dict, token: str | None) -> None:
        """Adds the spoken story to a listening fan's phone cue, as a private link."""
        if not listens(agent) or not token:
            return
        fields = cue["fields"]
        text = f"{fields['headline']}. {fields['line']}"
        clip = self.prepare(room, agent.agent_id, text, cue.get("lang", "en"))
        fields["audio"] = f"/rooms/{room}/audio/{clip}.mp3?fan={agent.agent_id}&token={token}"

    def allowed(self, room: str, clip: str, fan: str) -> bool:
        return fan in self.listeners.get((room, clip), set())

    async def audio(self, clip: str) -> bytes | None:
        task = self.clips.get(clip)
        return await task if task else None


def narrator_from_env() -> Narrator | None:
    speech = AzureSpeech.from_env()
    return Narrator(speech) if speech else None
