import { decisive, goal, regain, scorer, shot, shotDistance } from "../../fixtures/goal";
import { candidates } from "../../fixtures/room";

/**
 * The studio's picture of the demo match, Kestrel FC v Ashvale Athletic, 24 seconds after Okafor's goal.
 * The cues and their facts are the match's own (the engine's event feed and the origins investigation). The
 * room counts are a simulated rollout: synthetic aggregates shaped to agree with the demo room's decision,
 * and they grow a little each second, as rooms that are behind live reach the goal.
 */

/** Where a cue is on its way to the rooms. "withdrawn" is the producer pulling it after a VAR call or an error. */
export type CueState = "drafted" | "checked" | "armed" | "on-tvs" | "done" | "withdrawn";

export const stateLabel: Record<CueState, string> = {
  drafted: "Drafted",
  checked: "Checked",
  armed: "Armed",
  "on-tvs": "On TVs",
  done: "Done",
  withdrawn: "Withdrawn",
};

export interface LanguageVersion {
  lang: string;
  name: string;
  /** Missing versions fall back to English captions in that language's rooms. */
  headline?: string;
}

export interface Fact {
  claim: string;
  sources: string[];
  /** "feed" claims are matched to the event feed; "model" claims are our own estimate, kept off air. */
  checkedBy: "feed" | "model";
}

export type Destination = "all" | "one-club" | "language";

export interface StudioCue {
  id: string;
  minute: string;
  title: string;
  kind: string;
  state: CueState;
  /** One plain line under the cue in the lane. */
  note: string;
  headline?: string;
  line?: string;
  languages: LanguageVersion[];
  facts: Fact[];
}

/** A match clock some seconds after another one: plus("61:41", 9) is "61:50". */
export function plus(clock: string, seconds: number): string {
  const [m = 0, s = 0] = clock.split(":").map(Number);
  const total = m * 60 + s + seconds;
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/** The studio's clock when the page opens: the goal has just gone in, and its cue is on TVs. */
export const MATCH_CLOCK = plus(goal.goalClock, 24);
export const LIVE_CUE = "where-it-started";

const passes = goal.chain.filter((a) => a.type === "pass");
const presses = goal.chain.filter((a) => a.type === "press");

/** The match so far: earlier cues the lane folds into one chip. */
export const earlierCues = [
  { minute: "7:30", title: "Gilchrist's opener" },
  { minute: "35:15", title: "Gilchrist's second" },
  { minute: "38:46", title: "Okafor's first" },
  { minute: "47:15", title: "Okafor before the break" },
  { minute: "48:46", title: "Moreau pulls one back" },
  { minute: "58:08", title: "VAR: Asante's goal ruled out" },
];

/** What's on, what's next. The live cue's facts come straight from the origins investigation. */
export const cues: StudioCue[] = [
  {
    id: LIVE_CUE,
    minute: goal.goalClock,
    title: goal.copy.en_headline,
    kind: "Goal origin",
    state: "on-tvs",
    note: "Fair to both clubs",
    headline: goal.copy.en_headline,
    line: goal.copy.en_line,
    languages: [
      { lang: "en", name: "English", headline: goal.copy.en_headline },
      { lang: "es", name: "Spanish", headline: goal.copy.es_headline },
      // No Arabic or Polish writer yet: these rooms get English captions until a reviewed version exists.
      { lang: "ar", name: "Arabic" },
      { lang: "pl", name: "Polish" },
    ],
    facts: [
      { claim: `${regain.player} won the ball on halfway`, sources: [regain.id], checkedBy: "feed" },
      {
        claim: `${passes.length} passes: ${passes.map((p) => p.player).join(", ")}`,
        sources: passes.map((p) => p.id),
        checkedBy: "feed",
      },
      { claim: `${scorer} scored at ${goal.goalClock}`, sources: [shot.id], checkedBy: "feed" },
      {
        claim: `${decisive.label} added the most possession value of any action`,
        sources: [decisive.id, "value model"],
        checkedBy: "model",
      },
    ],
  },
  {
    id: "keepers-side",
    minute: plus(goal.goalClock, 20),
    title: "The finish from the keeper's side",
    kind: "Replay angle",
    state: "armed",
    note: "Next, once the TVs are free",
    languages: [
      { lang: "en", name: "English", headline: `${scorer} from ${shotDistance} metres` },
      { lang: "es", name: "Spanish", headline: `${scorer} desde ${shotDistance} metros` },
    ],
    facts: [{ claim: `Shot from ${shotDistance} metres`, sources: [shot.id], checkedBy: "feed" }],
  },
  {
    id: "pressing-map",
    minute: plus(goal.goalClock, 60),
    title: candidates["kestrel-pressing-map"]?.title ?? "Kestrel's pressing map",
    kind: "Shape",
    state: "checked",
    note: `Kestrel-only rooms. ${presses.map((p) => p.player).join(" and ")} on Lund`,
    languages: [{ lang: "en", name: "English" }],
    facts: [],
  },
  {
    id: "kestrel-legs",
    minute: "75:00",
    title: "How long Kestrel can keep pressing",
    kind: "Trend",
    state: "drafted",
    note: "For the last quarter of an hour",
    languages: [],
    facts: [],
  },
];

/* --- The simulated rollout ------------------------------------------------------------------------------ */

/** Rooms keep reaching the goal for a while (the median room is 38 s behind live): counts grow to full. */
export const reached = (t: number) => Math.min(1, 0.9 + (0.1 * t) / 40);

const scale = (n: number, t: number) => Math.round(n * reached(t));

/** What happened to the live cue across every room that received it. The parts add up to the rooms. */
export function rollout(t: number) {
  const onTv = scale(29_486, t);
  const otherPick = scale(6_140, t);
  const behind = scale(2_904, t);
  const tooSoon = scale(2_678, t);
  return {
    onTv,
    otherPick,
    held: behind + tooSoon,
    rooms: onTv + otherPick + behind + tooSoon,
    /** Phones that got it privately because their room showed something else, or a fan asked for it there. */
    phones: scale(38_912, t),
  };
}

/** Who is on the sofa, by room. */
export function sofa(t: number) {
  const { rooms } = rollout(t);
  const both = scale(18_330, t);
  const kestrel = scale(16_912, t);
  return [
    { id: "both", label: "Both clubs", n: both, colour: "var(--signal)" },
    { id: "kestrel", label: "Kestrel fans only", n: kestrel, colour: "var(--club-kestrel)" },
    { id: "ashvale", label: "Ashvale fans only", n: rooms - both - kestrel, colour: "var(--club-ashvale)" },
  ];
}

/** How the fans in those rooms like to watch, as each told their helper (counted per fan, not per room). */
export function watchStyle(t: number) {
  return [
    { id: "simple", label: "Simple", n: scale(46_180, t), colour: "var(--sun)" },
    { id: "numbers", label: "The numbers", n: scale(31_540, t), colour: "var(--sky)" },
    { id: "kids", label: "Kids", n: scale(19_150, t), colour: "var(--pitch)" },
    { id: "listen", label: "Listening", n: scale(15_770, t), colour: "var(--pink)" },
  ];
}

/** Caption language, by room. Welsh shows how a small group stays hidden behind the privacy minimum. */
export function languages(t: number) {
  const { rooms } = rollout(t);
  const rest = [
    { id: "es", label: "Spanish", n: scale(4_102, t), colour: "var(--sun)", ready: true },
    { id: "ar", label: "Arabic", n: scale(1_911, t), colour: "var(--pitch)", ready: false },
    { id: "pl", label: "Polish", n: scale(1_325, t), colour: "var(--pink)", ready: false },
    { id: "cy", label: "Welsh", n: 31, colour: "var(--line-strong)", ready: false },
  ];
  const en = rooms - rest.reduce((sum, l) => sum + l.n, 0);
  return [{ id: "en", label: "English", n: en, colour: "var(--sky)", ready: true }, ...rest];
}

/** No slice smaller than this is ever shown, so nobody can be picked out of a count. */
export const PRIVACY_MINIMUM = 50;

/* --- What rooms want right now ------------------------------------------------------------------------- */

export type Answer = "on-tvs" | "armed" | "checked" | "drafted" | "withdrawn" | "none";

export interface Demand {
  id: string;
  title: string;
  /** Which cue answers it, if any. "none" is unmet demand: fans want it and the studio has nothing to send. */
  answer: Answer;
  asks: number;
}

/** Deterministic wobble, so the race moves but every visit sees the same match. */
const wobble = (t: number, phase: number, size: number) => Math.round(Math.sin(t / 6 + phase) * size);

/**
 * Asks from helpers in the last two minutes, by what they asked for. As the replay ends, interest moves from
 * where it started to the finish itself, and to whether Okafor was onside.
 */
export function demand(t: number, drafted: boolean): Demand[] {
  const s = Math.min(t, 60);
  return [
    { id: "where", title: "Where it started", answer: "on-tvs", asks: 14_200 - 95 * s + wobble(t, 0, 120) },
    {
      id: "keeper",
      title: "The finish from the keeper's side",
      answer: "armed",
      asks: 11_400 + 70 * s + wobble(t, 1, 140),
    },
    {
      id: "onside",
      title: "Was Okafor onside?",
      answer: drafted ? "drafted" : "none",
      asks: 9_800 + 85 * s + wobble(t, 2, 160),
    },
    {
      id: "season",
      title: "Okafor's goals this season",
      answer: "none",
      asks: 6_300 + 30 * s + wobble(t, 3, 90),
    },
    { id: "pressing", title: "Kestrel's pressing map", answer: "checked", asks: 7_900 + wobble(t, 4, 110) },
    {
      id: "chances",
      title: "Ashvale's chances so far",
      answer: "none",
      asks: 2_100 + 8 * s + wobble(t, 5, 60),
    },
  ].sort((a, b) => b.asks - a.asks) as Demand[];
}

/* --- Followed players ---------------------------------------------------------------------------------- */

export interface Followed {
  name: string;
  number: number;
  club: "kestrel" | "ashvale";
  follows: number;
  /** New follows since the goal went in. */
  since: number;
}

/** Fans who told their helper to follow a player. Okafor's count jumps after his goal. */
export function followed(t: number): Followed[] {
  const s = Math.min(t, 90);
  const okaforSince = 5_900 + 40 * s;
  return (
    [
      { name: "Okafor", number: 9, club: "kestrel", follows: 15_200 + okaforSince, since: okaforSince },
      { name: "E. Gilchrist", number: 11, club: "kestrel", follows: 12_940 + 2 * s, since: 30 + 2 * s },
      { name: "Moreau", number: 9, club: "ashvale", follows: 8_710 + s, since: 12 + s },
      { name: "Mensah", number: 6, club: "kestrel", follows: 4_980 + 14 * s, since: 820 + 14 * s },
      { name: "Asante", number: 7, club: "ashvale", follows: 4_120, since: 0 },
    ] as Followed[]
  ).sort((a, b) => b.follows - a.follows);
}

/* --- The match so far: asks per minute ----------------------------------------------------------------- */

/** Goals and the VAR call, on the strip. */
export const moments = [
  { minute: 7, label: "Gilchrist 1–0" },
  { minute: 35, label: "Gilchrist 2–0" },
  { minute: 38, label: "Okafor 3–0" },
  { minute: 47, label: "Okafor 4–0" },
  { minute: 48, label: "Moreau 4–1" },
  { minute: 58, label: "VAR: no goal" },
  { minute: 61, label: "Okafor 5–1" },
];

const hash = (n: number) => {
  const x = Math.sin(n * 12.9898) * 43_758.5453;
  return x - Math.floor(x);
};

/** Asks per minute for minutes 1 to 90. Minutes still to come are null. */
export function asksPerMinute(nowMinute: number): (number | null)[] {
  return Array.from({ length: 90 }, (_, i) => {
    const minute = i + 1;
    if (minute > nowMinute + 1) return null;
    const base = 2_000 + hash(minute) * 1_800;
    const spike = moments.reduce((sum, m) => {
      const after = minute - m.minute;
      return after >= 0 && after < 5 ? sum + 26_000 * 0.55 ** after : sum;
    }, 0);
    return Math.round(base + spike);
  });
}

export const percent = (part: number, whole: number) => (whole ? Math.round((part / whole) * 100) : 0);
export const count = (n: number) => n.toLocaleString("en-GB");
/** A count of rooms, or the privacy minimum's words when the group is too small to show. */
export const rooms = (n: number) => (n < PRIVACY_MINIMUM ? `fewer than ${PRIVACY_MINIMUM}` : count(n));
