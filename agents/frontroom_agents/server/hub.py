"""Who is connected to a room, and how messages reach them.

Every screen in a room holds one WebSocket: the TV, each fan's phone, the room view and the studio. The hub
keeps phones private: a message for one fan's phone goes to that phone only.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

SEND_TIMEOUT_S = 2.0


class Socket(Protocol):
    async def send_text(self, data: str) -> None: ...


@dataclass
class Hub:
    rooms: dict[str, dict[str, set[Socket]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(set))
    )
    """room id -> screen ("tv", "phone:rob", "room", "studio") -> sockets."""

    def join(self, room: str, screen: str, socket: Socket) -> None:
        self.rooms[room][screen].add(socket)

    def leave(self, room: str, screen: str, socket: Socket) -> None:
        self.rooms[room][screen].discard(socket)

    def phones(self, room: str) -> list[str]:
        return [
            s.removeprefix("phone:")
            for s, sockets in self.rooms[room].items()
            if s.startswith("phone:") and sockets
        ]

    async def send(self, room: str, screen: str, message: dict[str, Any]) -> None:
        text = json.dumps(message, default=str)
        sockets = self.rooms.get(room, {}).get(screen, set())
        for socket in list(sockets):
            try:
                # A screen that stops reading must not hold up the TV and the other phones.
                await asyncio.wait_for(socket.send_text(text), timeout=SEND_TIMEOUT_S)
            except Exception:
                sockets.discard(socket)

    async def broadcast(
        self, room: str, message: dict[str, Any], screens: tuple[str, ...] | None = None
    ) -> None:
        """To every screen in the room, or the named ones. Phones are included only when named."""
        targets = screens or tuple(s for s in self.rooms.get(room, {}) if not s.startswith("phone:"))
        for screen in targets:
            await self.send(room, screen, message)
