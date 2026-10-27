import type { Bid, Cue, Decision, Insight } from "@frontroom/protocol";
import { useEffect, useState } from "react";
import { bids as demoBids, decision as demoDecision } from "../fixtures/room";

/**
 * The live connection to a room on the room server (agents/frontroom_agents/server).
 *
 * Every surface works without it: by default it shows the demo room from the fixtures, so screenshots and
 * the video are repeatable. Add `?live=1` (and optionally `&room=4821`) to follow a real room instead.
 */

export type Screen = "tv" | "room" | "studio" | "phone" | "demo";

export interface TraceStep {
  role: string;
  summary: string;
  ms: number;
}

export type RoomMessage =
  | { type: "joined"; fans: string[]; bothClubs: boolean }
  | { type: "investigating"; shotId: string }
  | { type: "step"; role: string; state: "working" | "done"; summary?: string; ms?: number }
  | { type: "insight"; insight: Insight; copy: Record<string, string>; trace: TraceStep[] }
  | { type: "decision"; decision: Decision; bids: Bid[]; dropped: string[] }
  | { type: "cue"; cue: Cue };

/** In development the room server runs beside Vite; deployed, it serves this app from the same origin. */
const SERVER =
  import.meta.env.VITE_ROOM_SERVER ??
  (import.meta.env.DEV ? "http://localhost:8787" : window.location.origin);

export function liveRoom(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get("live") === "1" ? (params.get("room") ?? "4821") : null;
}

export const serverUrl = (path: string) => new URL(path, SERVER).toString();

/**
 * Every message this screen has received, newest last. Empty when not live.
 * A phone's cues are private: it connects only with the token its fan got on joining.
 */
export function useRoomFeed(screen: Screen, fan?: string, token?: string): RoomMessage[] {
  const [messages, setMessages] = useState<RoomMessage[]>([]);
  useEffect(() => {
    const room = liveRoom();
    if (!room || (screen === "phone" && !token)) return;
    const url = new URL(`/rooms/${room}/ws`, SERVER.replace(/^http/, "ws"));
    url.searchParams.set("screen", screen);
    if (fan) url.searchParams.set("fan", fan);
    if (token) url.searchParams.set("token", token);
    const socket = new WebSocket(url);
    socket.onmessage = (event) => setMessages((all) => [...all, JSON.parse(event.data) as RoomMessage]);
    return () => socket.close();
  }, [screen, fan, token]);
  return messages;
}

export function latest<T extends RoomMessage["type"]>(
  messages: RoomMessage[],
  type: T,
): Extract<RoomMessage, { type: T }> | undefined {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message?.type === type) return message as Extract<RoomMessage, { type: T }>;
  }
  return undefined;
}

/** The decision to show: the room's latest one when live, otherwise the demo room's. */
export function useDecision(screen: Screen): { bids: Bid[]; decision: Decision; dropped: string[] } {
  const live = latest(useRoomFeed(screen), "decision");
  return live
    ? { bids: live.bids, decision: live.decision, dropped: live.dropped }
    : { bids: demoBids, decision: demoDecision, dropped: [] };
}
