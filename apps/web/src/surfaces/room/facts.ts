import type { Bid, Decision } from "@frontroom/protocol";
import { candidates, type Fan, fans } from "../../fixtures/room";

/** Everything the room view says about one decision, worked out once from the Director's output. */

type Constraint = NonNullable<Decision["candidates"][number]["struckBy"]>;

/** Each house rule in plain words: a short label for tables, and a clause that finishes "…but ___". */
export const rules: Record<Constraint, { short: string; clause: string }> = {
  "neutral-framing": {
    short: "Not while both clubs are here",
    clause: "it favours one club and both clubs are in the room",
  },
  "spoiler-gate": {
    short: "Not yet: it hasn't happened on this TV",
    clause: "it hasn't happened on this TV yet",
  },
  "var-hold": { short: "Not during a VAR check", clause: "the referee is checking VAR" },
  "one-overlay": { short: "Something else is already on", clause: "something else is already on the TV" },
  "min-gap": { short: "Too soon after the last one", clause: "the TV needs a break between overlays" },
  "captions-stay": { short: "It would cover the captions", clause: "it would cover the captions" },
};

/** Short names for the board and the seat labels, where the full titles don't fit. */
const shortTitles: Record<string, string> = {
  "where-it-started": "Where it started",
  "kestrel-pressing-map": "Pressing map",
  "keepers-view": "Keeper's view",
};
export const shortTitle = (id: string) => shortTitles[id] ?? candidates[id]?.title ?? id;
export const title = (id: string) => candidates[id]?.title ?? id;

/** Why each agent leaned the way it did, from what its fan said when they joined. Operator view only. */
const reasonByDepth: Record<Fan["depth"], string> = {
  analyst: "asked for shape and numbers",
  casual: "asked to keep it simple",
  kid: "is 10 and likes goals",
  audio: "asked to be talked through it",
};
export const agentReason = (fan: Fan) => `${fan.name} ${reasonByDepth[fan.depth]}`;

/** Whole-number percentages that always add up to 100 (largest remainder). */
export function shares(values: number[]): number[] {
  const total = values.reduce((sum, v) => sum + v, 0);
  if (total === 0) return values.map(() => 0);
  const exact = values.map((v) => (v / total) * 100);
  const floors = exact.map(Math.floor);
  let left = 100 - floors.reduce((sum, v) => sum + v, 0);
  const byRemainder = exact.map((v, i) => ({ i, r: v - Math.floor(v) })).sort((a, b) => b.r - a.r);
  for (const { i } of byRemainder) {
    if (left <= 0) break;
    floors[i] = (floors[i] ?? 0) + 1;
    left -= 1;
  }
  return floors;
}

export interface CandidateRow {
  id: string;
  title: string;
  askedBy: string[];
  rawShare: number;
  fairShare: number;
  struckBy?: Constraint;
  won: boolean;
}

export interface RoomFacts {
  decision: Decision;
  rows: CandidateRow[];
  winner: CandidateRow | undefined;
  /** The overlay with the most weighted support, whether or not it was allowed on. */
  mostWanted: CandidateRow;
  bids: Bid[];
  /** Fans whose agent missed the bid deadline; their bids are left out of this decision. */
  dropped: Set<string>;
  deliveredPrivately: Map<string, string>;
}

export const weightOf = (decision: Decision, fanId: string) =>
  decision.weights.find((w) => w.agentId === fanId);

/**
 * The decision as the room view shows it. With nobody dropped this is exactly the Director's output.
 * With a dropped agent, it replays the same arithmetic as director.py (weighted support, house rules
 * first, earliest then id on ties) without that agent's bids, so the view can show a late agent.
 */
export function roomFacts(bids: Bid[], decision: Decision, dropped: Set<string> = new Set()): RoomFacts {
  const inPlay = withinBudget(bids.filter((b) => !dropped.has(b.agentId)));
  const raw = (id: string) => inPlay.filter((b) => b.candidateId === id).reduce((s, b) => s + b.utility, 0);
  const fair = (id: string) =>
    inPlay
      .filter((b) => b.candidateId === id)
      .reduce((s, b) => s + (weightOf(decision, b.agentId)?.weight ?? 1) * b.utility, 0);

  const scored = decision.candidates.map((c) => ({
    id: c.candidateId,
    raw: dropped.size ? raw(c.candidateId) : c.rawScore,
    fair: dropped.size ? fair(c.candidateId) : c.fairScore,
    struckBy: c.struckBy,
  }));
  const eligible = scored.filter((c) => !c.struckBy && c.fair > 0);
  const winnerId = dropped.size
    ? eligible.reduce<(typeof eligible)[number] | undefined>(
        (best, c) => (!best || c.fair > best.fair ? c : best),
        undefined,
      )?.id
    : decision.candidates.find((c) => c.won)?.candidateId;

  const rawShares = shares(scored.map((c) => c.raw));
  const fairShares = shares(scored.map((c) => c.fair));
  const rows: CandidateRow[] = scored.map((c, i) => ({
    id: c.id,
    title: title(c.id),
    askedBy: (decision.candidates.find((d) => d.candidateId === c.id)?.askedBy ?? []).filter(
      (fan) => !dropped.has(fan),
    ),
    rawShare: rawShares[i] ?? 0,
    fairShare: fairShares[i] ?? 0,
    ...(c.struckBy ? { struckBy: c.struckBy } : {}),
    won: c.id === winnerId,
  }));

  // Each fan whose favourite didn't make the TV gets it on their own phone instead.
  const deliveredPrivately = new Map<string, string>();
  for (const fan of fans) {
    const favourite = inPlay
      .filter((b) => b.agentId === fan.id)
      .reduce<Bid | undefined>((best, b) => (!best || b.utility > best.utility ? b : best), undefined);
    if (favourite && favourite.candidateId !== winnerId)
      deliveredPrivately.set(fan.id, favourite.candidateId);
  }

  return {
    decision,
    rows,
    winner: rows.find((r) => r.won),
    mostWanted: rows.reduce((best, r) => (r.fairShare > best.fairShare ? r : best)),
    bids: inPlay,
    dropped,
    deliveredPrivately,
  };
}

/** Each agent's bids scaled to add up to at most 1, as director.py does before it counts anything. */
function withinBudget(bids: Bid[]): Bid[] {
  const totals = new Map<string, number>();
  for (const b of bids) totals.set(b.agentId, (totals.get(b.agentId) ?? 0) + b.utility);
  return bids.map((b) => ({ ...b, utility: b.utility * Math.min(1, 1 / (totals.get(b.agentId) || 1)) }));
}

/** `?dropped=sam` shows the room as it would decide if Sam's agent missed the deadline. */
export function droppedFromUrl(): Set<string> {
  const ids = new URLSearchParams(window.location.search).get("dropped");
  return new Set(ids ? ids.split(",").filter((id) => fans.some((f) => f.id === id)) : []);
}

/**
 * Seats on the sofa, left to right. Each fan sits under the overlays they leaned towards,
 * so the bid arrows cross as little as possible.
 */
export function seatOrder(candidateX: Record<string, number>, bids: Bid[]): Fan[] {
  const lean = (fan: Fan) => {
    const own = bids.filter((b) => b.agentId === fan.id);
    const total = own.reduce((sum, b) => sum + b.utility, 0);
    return own.reduce((sum, b) => sum + b.utility * (candidateX[b.candidateId] ?? 0), 0) / (total || 1);
  };
  return [...fans].sort((a, b) => lean(a) - lean(b));
}

export const minutes = (seconds: number) => {
  const m = Math.round(seconds / 60);
  return m === 1 ? "1 minute" : `${m} minutes`;
};

/** Joins names the way people say them: "Rob", "Rob and Sam", "Rob, Sam and Ana". */
export function listNames(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}
