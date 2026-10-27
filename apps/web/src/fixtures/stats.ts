import stats from "./player-stats.json";
import type { ClubId, Fan } from "./room";

/**
 * Every player's and team's numbers up to Okafor's goal (61:41), measured from the demo match's 25 Hz
 * tracking and event feed. The phones' "my number" and player focus read them.
 */

export type Metric = "distance" | "top-speed" | "shots-on-target" | "pass-accuracy" | "possession";

interface PlayerStats {
  name: string;
  label: string;
  side: "home" | "away";
  number: number;
  starting: boolean;
  distanceKm: number;
  topSpeedKmh: number;
  sprints: number;
  shots: number;
  shotsOnTarget: number;
  passAccuracy: number | null;
  inTheMove?: { metres: number; topSpeedKmh: number };
}

interface TeamStats {
  name: string;
  short: string;
  possession: number;
  shots: number;
  shotsOnTarget: number;
  passAccuracy: number | null;
  distanceKm: number;
}

const players = stats.players as Record<string, PlayerStats>;
const teams = stats.teams as Record<"home" | "away", TeamStats>;

/** Kestrel are at home in the demo match, Ashvale away. */
const sideOf: Record<ClubId, "home" | "away"> = { kestrel: "home", ashvale: "away" };

/** The starting players fans can follow, home first, by the name they'd use. */
export const followable = Object.values(players)
  .filter((p) => p.starting && p.number !== 1)
  .map((p) => ({ label: p.label, side: p.side, number: p.number }));

export const playerByLabel = (label: string): PlayerStats | undefined =>
  Object.values(players).find((p) => p.label === label);

export const metricNames: Record<"en" | "es", Record<Metric, string>> = {
  en: {
    distance: "Distance run",
    "top-speed": "Top speed",
    "shots-on-target": "Shots on target",
    "pass-accuracy": "Pass accuracy",
    possession: "Possession",
  },
  es: {
    distance: "Distancia",
    "top-speed": "Velocidad máxima",
    "shots-on-target": "Tiros a puerta",
    "pass-accuracy": "Precisión de pase",
    possession: "Posesión",
  },
};

function format(metric: Metric, value: number | null, lang: "en" | "es"): string {
  if (value === null) return "–";
  const decimal = (n: number) => n.toLocaleString(lang === "es" ? "es" : "en-GB");
  switch (metric) {
    case "distance":
      return `${decimal(value)} km`;
    case "top-speed":
      return `${decimal(value)} km/h`;
    case "pass-accuracy":
    case "possession":
      return `${value}%`;
    case "shots-on-target":
      return String(value);
  }
}

/**
 * A fan's one number: for the first player they follow when it's a player's number, otherwise for their club
 * (or the home side when they have none). Possession is only ever a team's.
 */
export function myNumber(fan: Fan): { name: string; whose: string; value: string } | undefined {
  if (!fan.metric) return undefined;
  const name = metricNames[fan.lang][fan.metric];
  const player = fan.follows?.[0] ? playerByLabel(fan.follows[0]) : undefined;
  if (player && fan.metric !== "possession") {
    const value = {
      distance: player.distanceKm,
      "top-speed": player.topSpeedKmh,
      "shots-on-target": player.shotsOnTarget,
      "pass-accuracy": player.passAccuracy,
    }[fan.metric];
    return { name, whose: player.name, value: format(fan.metric, value, fan.lang) };
  }
  const team = teams[sideOf[fan.club]];
  const value = {
    distance: team.distanceKm,
    "top-speed": null,
    "shots-on-target": team.shotsOnTarget,
    "pass-accuracy": team.passAccuracy,
    possession: team.possession,
  }[fan.metric];
  return { name, whose: team.short, value: format(fan.metric, value, fan.lang) };
}

/** A followed player's part in the goal's move and their night so far, in the fan's language. */
export function playerFocus(label: string, lang: "en" | "es"): { name: string; line: string } | undefined {
  const p = playerByLabel(label);
  if (!p) return undefined;
  const km = p.distanceKm.toLocaleString(lang === "es" ? "es" : "en-GB");
  const move = p.inTheMove ? p.inTheMove.metres : undefined;
  const line =
    lang === "es"
      ? `${move !== undefined ? `${move} m en la jugada del gol. ` : ""}${km} km y ${p.sprints} sprints esta noche.`
      : `${move !== undefined ? `${move} m in the goal's move. ` : ""}${km} km and ${p.sprints} sprints tonight.`;
  return { name: p.name, line };
}

export { players as playerStats, teams as teamStats };
