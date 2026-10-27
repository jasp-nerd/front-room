import type { Bid, Decision } from "@frontroom/protocol";
import { candidates, type Fan, fanById, fans } from "../../fixtures/room";
import { copy } from "../phone/copy";

/** "Rob", "Rob and Sam", "Rob, Leo and Sam". */
export function listNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

const nameOf = (id: string) => fanById(id).name;

export const titleOf = (candidateId: string) => candidates[candidateId]?.title ?? candidateId;

/** How long a beat stays up: time to read it, never less than three seconds. */
export function holdFor(...texts: string[]): number {
  const words = texts.join(" ").split(/\s+/).filter(Boolean).length;
  return Math.max(3_000, 1_500 + 300 * words);
}

/** The fans on the sofa supporting the club with fewer fans there (in the demo: Ana, for Ashvale). */
export function outnumbered(present: Fan[]): Fan[] {
  const kestrel = present.filter((f) => f.club === "kestrel");
  const ashvale = present.filter((f) => f.club === "ashvale");
  if (!kestrel.length || !ashvale.length) return [];
  return kestrel.length <= ashvale.length ? kestrel : ashvale;
}

/** Each helper's favourite: what it asks the TV for. */
export function favourites(bids: Bid[]): Map<string, string> {
  const best = new Map<string, Bid>();
  for (const bid of bids) {
    const held = best.get(bid.agentId);
    if (!held || bid.utility > held.utility) best.set(bid.agentId, bid);
  }
  return new Map([...best].map(([fan, bid]) => [fan, bid.candidateId]));
}

/** What a helper says on its fan's phone when it asks for the TV, in the fan's language. */
export function askLine(fan: Fan, candidateId: string): string {
  const title = copy[fan.lang].candidates[candidateId] ?? titleOf(candidateId);
  return fan.lang === "es"
    ? `¿Ponemos ${title.toLowerCase()} en la tele?`
    : `Can we have ${title} on the TV?`;
}

/** Who gets a pick that missed the TV on their own phone. */
export function ownersOf(decision: Decision, candidateId: string): string[] {
  return decision.deliveredPrivately.filter((d) => d.candidateId === candidateId).map((d) => d.agentId);
}

const ruleWords: Record<string, string> = {
  "one-overlay": "Something else is already on the TV",
  "min-gap": "The TV needs a short break first",
  "spoiler-gate": "This TV hasn't shown the goal yet",
  "var-hold": "It's waiting for the VAR check",
  "captions-stay": "It would cover the captions",
};

/** Why a pick missed the TV and where it goes instead, in the words you'd use on the sofa. */
export function stampFor(decision: Decision, candidateId: string, present: Fan[]): string {
  const c = decision.candidates.find((x) => x.candidateId === candidateId);
  const owners = ownersOf(decision, candidateId).map(nameOf);
  const goes = owners.length ? `so it goes to ${listNames(owners)}'s phone` : "so it stays off the TV";
  if (c?.struckBy === "neutral-framing") {
    const favours = candidates[candidateId]?.favours;
    const rivals = present.filter((f) => f.club !== favours).map((f) => f.name);
    const isAre = rivals.length === 1 ? "is" : "are";
    return `${listNames(rivals)} ${isAre} on the sofa too, ${goes}.`;
  }
  if (c?.struckBy) return `${ruleWords[c.struckBy] ?? "A house rule held it back"}, ${goes}.`;
  const winner = decision.candidates.find((x) => x.won);
  return winner
    ? `The room wanted ${titleOf(winner.candidateId)} more, ${goes}.`
    : `It didn't fit the TV this time, ${goes}.`;
}

/** Pip's call, in one line: why the winner is fair to this sofa. */
export function whyItWon(decision: Decision, present: Fan[]): string {
  const winner = decision.candidates.find((c) => c.won);
  if (!winner) return "Nothing fits the TV right now, so everything goes to the phones.";
  const away = outnumbered(present);
  if (away.length) {
    return `It's fair to ${listNames(away.map((f) => f.name))} too, so it goes on the TV.`;
  }
  const out = fans.filter((f) => !present.includes(f)).map((f) => f.name);
  const askers = (winner.askedBy ?? []).map(nameOf);
  const who = out.length ? `With ${listNames(out)} out of the room, everyone` : "Everyone";
  return `${who} here supports Kestrel, so a Kestrel pick is fine. ${listNames(askers)} wanted this one.`;
}

/**
 * Whether waiting longest actually tipped it: the winner would have lost on asks alone. Only then is it worth
 * saying.
 */
export function waitTipped(decision: Decision): string | undefined {
  const eligible = decision.candidates.filter((c) => !c.struckBy);
  const onAsksAlone = [...eligible].sort((a, b) => b.rawScore - a.rawScore)[0];
  const winner = decision.candidates.find((c) => c.won);
  if (!winner || !onAsksAlone || onAsksAlone.candidateId === winner.candidateId) return undefined;
  const [longest] = [...decision.weights].sort((a, b) => b.secondsWithoutScreen - a.secondsWithoutScreen);
  return longest
    ? `${nameOf(longest.agentId)} has waited longest for the TV, and that tipped it.`
    : undefined;
}

/** The label over a phone once it lights up. */
export function gotLine(decision: Decision, fanId: string): string {
  const own = decision.deliveredPrivately.find((d) => d.agentId === fanId);
  return own ? `Got ${titleOf(own.candidateId)}` : "Their pick is on the TV!";
}

/** The investigation's steps, as a line a fan can read while the replay plays. */
export function stepLine(role: string, summary: string | undefined): string {
  const text = (summary ?? "").trim();
  const first = (s: string, max = 70) => {
    const clause = s.split(/[.;:]/)[0]?.trim() ?? s;
    return clause.length > max ? `${clause.slice(0, max - 1)}…` : clause;
  };
  switch (role) {
    case "extract":
      return text ? `Reading the match data: ${first(text)}` : "Reading the match data";
    case "hypothesis":
      return text ? `Investigator: ${first(text)}` : "An investigator is looking for where it started";
    case "experiment":
      return "Testing each pass and tackle with the value model";
    case "skeptic":
      return "A second agent is trying to prove it wrong";
    case "verify":
      return "Checking every claim against the event feed";
    case "writer":
      return text ? `Writing it up: “${text.split(" / ")[0]}”` : "Writing it up for the TV";
    case "check":
      return text === "passed" ? "Fact check passed" : "Fact-checking the words";
    default:
      return text;
  }
}

/** The fans whose club just conceded: in the demo, Ana. */
export const unhappy = (present: Fan[]) => present.filter((f) => f.club === "ashvale");

export { fans };
