import type { Bid, Decision } from "@frontroom/protocol";
import demo from "./demo-room.json";
import type { Metric } from "./stats";

/**
 * The demo room. Bids and the decision come straight from the Room Director
 * (`python -m frontroom_agents.room.demo`); everything below is what the phones know about their own fan.
 */

export type ClubId = "kestrel" | "ashvale";
export type Depth = "analyst" | "casual" | "kid" | "audio";

export interface Fan {
  id: string;
  name: string;
  club: ClubId;
  depth: Depth;
  lang: "en" | "es";
  /** What the fan told their agent when they joined, in their own words. */
  told: string;
  /** Players they follow, by the name fans use (fixtures/stats.ts). Their phone leads with that player. */
  follows?: string[];
  /** The one number they asked to keep in view. */
  metric?: Metric;
}

export const fans: Fan[] = [
  {
    id: "rob",
    name: "Rob",
    club: "kestrel",
    depth: "analyst",
    lang: "en",
    told: "Show me the shape. I want numbers. Pass accuracy is my thing.",
    metric: "pass-accuracy",
  },
  {
    id: "ana",
    name: "Ana",
    club: "ashvale",
    depth: "casual",
    lang: "es",
    told: "Solo lo importante, en español. Y la posesión.",
    metric: "possession",
  },
  {
    id: "leo",
    name: "Leo",
    club: "kestrel",
    depth: "kid",
    lang: "en",
    told: "I'm 10 and I like goals. Okafor is my favourite, he's the fastest!",
    follows: ["Okafor"],
    metric: "top-speed",
  },
  {
    id: "sam",
    name: "Sam",
    club: "kestrel",
    depth: "audio",
    lang: "en",
    told: "Big text. Talk me through it.",
  },
];

export const clubs: Record<ClubId, { name: string; short: string; colour: string; onColour: string }> = {
  kestrel: {
    name: "Kestrel FC",
    short: "KES",
    colour: "var(--club-kestrel)",
    onColour: "var(--on-club-kestrel)",
  },
  ashvale: {
    name: "Ashvale Athletic",
    short: "ASH",
    colour: "var(--club-ashvale)",
    onColour: "var(--on-club-ashvale)",
  },
};

export interface CandidateInfo {
  title: string;
  /** Which club the overlay favours, if any. */
  favours?: ClubId;
}

export const candidates: Record<string, CandidateInfo> = {
  "where-it-started": { title: "Where it started" },
  "kestrel-pressing-map": { title: "Kestrel's pressing map", favours: "kestrel" },
  "keepers-view": { title: "How Ashvale's keeper saw it", favours: "ashvale" },
  "player-okafor": { title: "Okafor in numbers", favours: "kestrel" },
};

export const bids = demo.bids as Bid[];
export const decision = demo.decision as Decision;

export const fanById = (id: string): Fan => {
  const fan = fans.find((f) => f.id === id);
  if (!fan) throw new Error(`No fan "${id}" in the demo room`);
  return fan;
};

/** Fans whose agent asked for the overlay that won the TV, as the Director counts them. */
export const askedForWinner = (): string[] => decision.candidates.find((c) => c.won)?.askedBy ?? [];

export const winnerId = (): string => decision.candidates.find((c) => c.won)?.candidateId ?? "";

/** What a fan's agent delivered to their phone because it didn't make the TV. */
export const privateDelivery = (fanId: string): string | undefined =>
  decision.deliveredPrivately.find((d) => d.agentId === fanId)?.candidateId;

/** Kit colours for drawing the demo match from above: Kestrel at home, Ashvale away. */
export const kits = {
  home: { fill: clubs.kestrel.colour, ink: clubs.kestrel.onColour },
  away: { fill: clubs.ashvale.colour, ink: clubs.ashvale.onColour },
};
