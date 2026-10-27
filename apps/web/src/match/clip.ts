import type { PitchPoint, TrackingFrame } from "@frontroom/protocol";
import type { PlayerLook, Telestration } from "./render";

/**
 * A goal from a SynthLeague match, exported from the engine: 25 Hz tracking in a compact form
 * (one array per frame: ball x, y, z, then x, y for each player in `players` order) and the scoring
 * possession's actions.
 */
export interface Clip {
  matchId: string;
  fps: number;
  period: 1 | 2;
  startClockMs: number;
  players: { id: string; side: "home" | "away"; number: number; name: string; keeper: boolean }[];
  frames: number[][];
  goal: { clockMs: number; scorer: string | null; side: "home" | "away" };
  chain: {
    id: string;
    type: string;
    clockMs: number;
    playerId: string | null;
    start: PitchPoint;
    end?: PitchPoint;
  }[];
}

export const clipLengthMs = (clip: Clip) => ((clip.frames.length - 1) / clip.fps) * 1000;

/** Frames either side used to measure a speed (a quarter of a second in all), smoothing tracking jitter. */
const SPEED_SPAN = 3;
/** A speed is shown as the fastest of the last half second, so a name tab that shows it stays readable. */
const SPEED_HOLD = 12;

/** Player `n`'s speed at frame `i` in m/s, from the movement across the frames around it. */
function speedAt(clip: Clip, n: number, i: number): number {
  const from = clip.frames[Math.max(i - SPEED_SPAN, 0)] ?? [];
  const to = clip.frames[Math.min(i + SPEED_SPAN, clip.frames.length - 1)] ?? [];
  const frames = Math.min(i + SPEED_SPAN, clip.frames.length - 1) - Math.max(i - SPEED_SPAN, 0);
  if (frames <= 0) return 0;
  const dx = (to[3 + 2 * n] ?? 0) - (from[3 + 2 * n] ?? 0);
  const dy = (to[4 + 2 * n] ?? 0) - (from[4 + 2 * n] ?? 0);
  return Math.hypot(dx, dy) / (frames / clip.fps);
}

function recentTopSpeed(clip: Clip, n: number, i: number): number {
  let top = 0;
  for (let k = Math.max(i - SPEED_HOLD, 0); k <= i; k += 1) top = Math.max(top, speedAt(clip, n, k));
  return top;
}

/** The match at `ms` into the clip, interpolated between the two nearest 25 Hz frames. */
export function frameAt(clip: Clip, ms: number): TrackingFrame {
  const position = Math.min(Math.max((ms / 1000) * clip.fps, 0), clip.frames.length - 1);
  const i = Math.floor(position);
  const a = clip.frames[i] ?? [];
  const b = clip.frames[Math.min(i + 1, clip.frames.length - 1)] ?? a;
  const f = position - i;
  const v = (k: number) => (a[k] ?? 0) + ((b[k] ?? 0) - (a[k] ?? 0)) * f;
  return {
    matchId: clip.matchId,
    frame: i,
    period: clip.period,
    clockMs: clip.startClockMs + ms,
    ball: { x: v(0), y: v(1), z: v(2) },
    players: clip.players.map((p, n) => ({
      playerId: p.id,
      side: p.side,
      x: v(3 + 2 * n),
      y: v(4 + 2 * n),
      speed: recentTopSpeed(clip, n, i),
    })),
  };
}

export const looks = (clip: Clip): Record<string, PlayerLook> =>
  Object.fromEntries(clip.players.map((p) => [p.id, { number: p.number, isKeeper: p.keeper }]));

/** Name tabs for the players who touched the ball in the move. */
export function storyLabels(clip: Clip): Record<string, string> {
  const ids = new Set(clip.chain.map((a) => a.playerId).filter((id): id is string => id !== null));
  return Object.fromEntries(clip.players.filter((p) => ids.has(p.id)).map((p) => [p.id, p.name]));
}

/** Actions with the ball: what the pass path is drawn through. Presses only get the ring. */
const ON_THE_BALL = new Set(["tackle", "interception", "pass", "cross", "dribble", "take_on", "shot"]);

/**
 * What the replay has drawn on the grass by match time `clockMs`: the ring where the move started (the first
 * press) once play reaches it, then the path, action by action, from the regain to the shot.
 */
export function telestrationAt(clip: Clip, clockMs: number): Telestration {
  const done = clip.chain.filter((a) => a.clockMs <= clockMs);
  if (done.length === 0) return {};
  const onBall = done.filter((a) => ON_THE_BALL.has(a.type));
  const path: PitchPoint[] = onBall.map((a) => a.start);
  const last = onBall[onBall.length - 1];
  if (last?.end && done.length === clip.chain.length) path.push(last.end);
  return { origin: clip.chain[0]?.start ?? path[0], ...(path.length > 1 ? { path } : {}) };
}

/**
 * Where a camera following play looks at `ms`: the ball's position averaged over the 3 seconds around that
 * moment, so it glides instead of jerking. A pure function of time, so any frozen frame is repeatable.
 * `centred` is the replay camera; the live camera (false) frames the ball the way the gantry does.
 */
export function followAt(clip: Clip, ms: number, centred = true): { x: number; y: number; z: number } {
  let x = 0;
  let y = 0;
  let n = 0;
  for (let t = ms - 1500; t <= ms + 1500; t += 100) {
    const ball = frameAt(clip, t).ball;
    x += ball.x;
    y += ball.y;
    n += 1;
  }
  // A replay looks just short of the ball, so play sits above the lower third; the live camera keeps the
  // ball a little upfield so the near touchline stays in shot.
  const across = centred ? y / n - 4 : (y / n) * 0.55 + 12;
  return {
    x: Math.min(Math.max(x / n, 20), 85),
    y: Math.min(Math.max(across, 16), centred ? 52 : 40),
    z: 0,
  };
}
