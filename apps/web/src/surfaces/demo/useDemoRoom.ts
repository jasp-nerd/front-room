import { useCallback, useEffect, useRef, useState } from "react";
import { type RoomMessage, serverUrl } from "../../live/feed";

/**
 * The demo's own room on the room server. Each visit gets a fresh room, so two visitors never play into each
 * other's sofa, and the address says which room it is (`?live=1&room=…`), which is how the phones find it.
 * The four fans join as the page opens (cheap: their words become profiles); the goal, and with it the model
 * calls, only runs when the visitor presses play.
 */
function roomForThisVisit(): string {
  const params = new URLSearchParams(window.location.search);
  const room = params.get("room") ?? `demo-${Math.random().toString(36).slice(2, 8)}`;
  if (params.get("live") !== "1" || params.get("room") !== room) {
    params.set("live", "1");
    params.set("room", room);
    window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
  }
  return room;
}

export type JoinState = "joining" | "ready" | "failed";

export function useDemoRoom() {
  const [room] = useState(roomForThisVisit);
  const [messages, setMessages] = useState<RoomMessage[]>([]);
  const [tokens, setTokens] = useState<Record<string, string>>({});
  const [join, setJoin] = useState<JoinState>("joining");
  /** Where this play's messages start: everything before it belongs to an earlier play. */
  const [playFrom, setPlayFrom] = useState<number | null>(null);
  const count = useRef(0);

  useEffect(() => {
    const url = new URL(`/rooms/${room}/ws`, serverUrl("/").replace(/^http/, "ws"));
    url.searchParams.set("screen", "demo");
    const socket = new WebSocket(url);
    socket.onmessage = (event) =>
      setMessages((all) => {
        const next = [...all, JSON.parse(event.data) as RoomMessage];
        count.current = next.length;
        return next;
      });
    return () => socket.close();
  }, [room]);

  const fill = useCallback(
    async (without?: string) => {
      setJoin("joining");
      try {
        const path = `/rooms/${room}/demo${without ? `?without=${without}` : ""}`;
        const response = await fetch(serverUrl(path), { method: "POST" });
        if (!response.ok) throw new Error(String(response.status));
        const joined = (await response.json()) as Record<string, { token: string }>;
        setTokens(Object.fromEntries(Object.entries(joined).map(([fan, j]) => [fan, j.token])));
        setJoin("ready");
      } catch {
        setJoin("failed");
      }
    },
    [room],
  );

  // Once per visit: a second join would hand the phones new tokens while they still hold the first ones.
  const filled = useRef(false);
  useEffect(() => {
    if (filled.current) return;
    filled.current = true;
    fill();
  }, [fill]);

  /** The goal goes in: from here the room server investigates, the helpers ask and Pip decides. */
  const play = useCallback(() => {
    setPlayFrom(count.current);
    fetch(serverUrl(`/rooms/${room}/goals/featured`), { method: "POST" }).catch(() => setJoin("failed"));
  }, [room]);

  /** Play the goal again, with everyone (a fresh room, so Pip starts from scratch) or with one fan away. */
  const again = useCallback(
    async (without?: string) => {
      setPlayFrom(null);
      await fill(without);
      play();
    },
    [fill, play],
  );

  const current = playFrom === null ? [] : messages.slice(playFrom);
  return { room, tokens, join, playing: playFrom !== null, messages: current, play, again };
}
