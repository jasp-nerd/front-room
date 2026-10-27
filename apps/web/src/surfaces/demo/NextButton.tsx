import { useEffect, useRef, useState } from "react";
import styles from "./DemoSurface.module.css";

interface NextButtonProps {
  /** How long the beat holds before moving on by itself. */
  holdMs: number;
  onNext: () => void;
}

const R = 25;
const CIRCUMFERENCE = 2 * Math.PI * R;

/** "Next", with a thin ring that fills as the beat runs out: the story moves on by itself, or on a click. */
export function NextButton({ holdMs, onNext }: NextButtonProps) {
  const [elapsed, setElapsed] = useState(0);
  const done = useRef(false);
  const next = useRef(onNext);
  next.current = onNext;

  // A wall-clock tick rather than animation frames, so a throttled tab still moves on in time.
  useEffect(() => {
    let last = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      const step = now - last;
      last = now;
      setElapsed((e) => Math.min(holdMs, e + step));
    }, 50);
    return () => window.clearInterval(timer);
  }, [holdMs]);

  useEffect(() => {
    if (elapsed >= holdMs && !done.current) {
      done.current = true;
      next.current();
    }
  }, [elapsed, holdMs]);

  return (
    <button
      type="button"
      className={styles.next}
      onClick={() => {
        if (done.current) return;
        done.current = true;
        next.current();
      }}
    >
      Next
      <svg viewBox="0 0 56 56" aria-hidden="true">
        <circle cx="28" cy="28" r={R} className={styles.nextTrack} />
        <circle
          cx="28"
          cy="28"
          r={R}
          className={styles.nextRing}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - elapsed / holdMs)}
        />
      </svg>
    </button>
  );
}
