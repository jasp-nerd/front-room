import { useEffect, useMemo, useState } from "react";
import type { Vec3 } from "./camera";
import { type Clip, clipLengthMs, followAt, frameAt, looks, storyLabels, telestrationAt } from "./clip";
import { type CameraPlacement, MatchCanvas } from "./MatchCanvas";

/** The replay camera: higher and further back than the live one, following the ball. */
const REPLAY_CAMERA: CameraPlacement = { back: -34, height: 58, fovDeg: 30 };

/**
 * Milliseconds into a clip, advancing with the screen's refresh. `?t=12000` in the address freezes it, so a
 * screenshot or a video frame of a moment is always the same picture.
 */
export function useClipTime(lengthMs: number, loop: boolean, atMs?: number, fromMs = 0, speed = 1): number {
  const fromUrl = new URLSearchParams(window.location.search).get("t");
  const frozen = fromUrl ?? (atMs === undefined ? null : String(atMs));
  const [ms, setMs] = useState(frozen ? Number(frozen) : fromMs);
  useEffect(() => {
    if (frozen) return;
    let start: number | undefined;
    let raf = 0;
    const tick = (now: number) => {
      start ??= now;
      const elapsed = fromMs + (now - start) * speed;
      setMs(loop ? elapsed % lengthMs : Math.min(elapsed, lengthMs));
      if (loop || elapsed < lengthMs) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [frozen, lengthMs, loop, fromMs, speed]);
  return ms;
}

/** The whole move, from the first press to the shot: where the camera settles once the goal is in. */
function wholeMove(clip: Clip): Vec3 {
  const xs = clip.chain.flatMap((a) => [a.start.x, a.end?.x ?? a.start.x]);
  const ys = clip.chain.flatMap((a) => [a.start.y, a.end?.y ?? a.start.y]);
  const mid = (values: number[]) => (Math.min(...values) + Math.max(...values)) / 2;
  // Aim a little short of the move, so the whole path sits above the lower third.
  return { x: mid(xs), y: mid(ys) - 8, z: 0 };
}

/** Wider lens for the settle, so the path from halfway to the goal fits in one picture. */
const SETTLE_CAMERA: CameraPlacement = { back: -30, height: 90, fovDeg: 40 };
const SETTLE_MS = 1600;

const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => t * t * (3 - 2 * t);

/**
 * The replay's camera at `ms`: it follows the ball during the move, then, from the goal on, glides back and
 * wide so the finished path shows end to end under the lower third.
 */
function cameraAt(clip: Clip, ms: number): { target: Vec3; camera: CameraPlacement } {
  const goalMs = clip.goal.clockMs - clip.startClockMs;
  const follow = followAt(clip, Math.min(ms, goalMs));
  const t = ease(Math.min(Math.max((ms - goalMs) / SETTLE_MS, 0), 1));
  if (t === 0) return { target: follow, camera: REPLAY_CAMERA };
  const settle = wholeMove(clip);
  return {
    target: { x: mix(follow.x, settle.x, t), y: mix(follow.y, settle.y, t), z: 0 },
    camera: {
      back: mix(REPLAY_CAMERA.back, SETTLE_CAMERA.back, t),
      height: mix(REPLAY_CAMERA.height, SETTLE_CAMERA.height, t),
      fovDeg: mix(REPLAY_CAMERA.fovDeg, SETTLE_CAMERA.fovDeg, t),
    },
  };
}

interface ClipReplayProps {
  clip: Clip;
  width: number;
  height: number;
  className?: string;
  /** Called with the replay's time, so overlays can come in when the move reaches them. */
  onTime?: (ms: number) => void;
  /** Hold the replay at this moment instead of playing it. */
  atMs?: number;
  /** Start again from the top when the replay ends, as a showcase does. */
  loop?: boolean;
  /** Start this far into the clip, and play this many times faster (the guided demo's quick replay). */
  fromMs?: number;
  speed?: number;
}

/** A goal's build-up played back on the broadcast camera, with the move drawn on the grass as it happens. */
export function ClipReplay({
  clip,
  width,
  height,
  className,
  onTime,
  atMs,
  loop = false,
  fromMs = 0,
  speed = 1,
}: ClipReplayProps) {
  const ms = useClipTime(clipLengthMs(clip), loop, atMs, fromMs, speed);
  const players = useMemo(() => looks(clip), [clip]);
  const labels = useMemo(() => storyLabels(clip), [clip]);
  const { target, camera } = cameraAt(clip, ms);
  const frame = frameAt(clip, ms);
  const telestration = telestrationAt(clip, frame.clockMs);

  useEffect(() => onTime?.(ms), [ms, onTime]);

  return (
    <MatchCanvas
      frame={frame}
      players={players}
      target={target}
      camera={camera}
      telestration={telestration}
      labels={labels}
      width={width}
      height={height}
      {...(className ? { className } : {})}
    />
  );
}
