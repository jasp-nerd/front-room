import type { PitchPoint, TrackingFrame } from "@frontroom/protocol";
import { type Clip, frameAt } from "../match/clip";
import demoGoal from "./demo-goal.json";
import goalClip from "./goal-clip.json";

/**
 * The demo goal as the engine played it and the origins investigation told it. Both files are written from
 * the engine's demo match; every screen reads its facts from here.
 */

export interface GoalAction {
  id: string;
  type: string;
  player: string;
  /** How the studio names it: "Okafor's run". */
  label: string;
  clockMs: number;
  start: PitchPoint;
  end?: PitchPoint;
  /** Possession value added against what a typical player would have done from the same spot. */
  value: number;
  interval: number[];
}

interface Score {
  home: number;
  away: number;
}

export interface DemoGoal {
  matchId: string;
  home: { name: string; short: string };
  away: { name: string; short: string };
  goalClock: string;
  regainClock: string;
  scoreBefore: Score;
  scoreAfter: Score;
  shotXg: number;
  passes: number;
  chain: GoalAction[];
  verdict: { kind: "decisive" | "shared"; top: string; value: number };
  copy: { en_headline: string; en_line: string; es_headline: string; es_line: string };
  trace: { role: string; summary: string; ms: number }[];
  insight: { id: string; eventIds: string[] };
  liveAgents: boolean;
}

export const goal = demoGoal as DemoGoal;
export const clip = goalClip as Clip;

const actionOf = (test: (a: GoalAction) => boolean): GoalAction => {
  const action = goal.chain.find(test);
  if (!action) throw new Error("demo-goal.json is missing an action the story needs");
  return action;
};

/** The press that started it, the tackle that won the ball, the action the model called decisive, the shot. */
export const firstPress = actionOf((a) => a.type === "press");
export const regain = actionOf((a) => a.type === "tackle" || a.type === "interception");
export const decisive = actionOf((a) => a.label === goal.verdict.top);
export const shot = actionOf((a) => a.type === "shot");
export const scorer = shot.player;

/** "5–1" */
export const scoreText = (score: Score) => `${score.home}–${score.away}`;

/** The match clock for a moment in the second half, as a scorebug shows it: 61:20. */
export function secondHalfClock(clockMs: number): string {
  const seconds = Math.floor(clockMs / 1000) + 45 * 60;
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Milliseconds into the replay clip at which a moment of the match happens. */
export const clipMs = (clockMs: number) => clockMs - clip.startClockMs;

/** The match as it stood at a moment of the move, from the engine's 25 Hz tracking. */
export const frameAtClock = (clockMs: number): TrackingFrame => frameAt(clip, clipMs(clockMs));

/** Distance from the goal line to where the shot was struck, in whole metres. */
export const shotDistance = Math.round(
  Math.hypot(shot.start.x - (shot.end && shot.end.x < 52.5 ? 0 : 105), shot.start.y - 34),
);
