import { useEffect, useState } from "react";

/** Where the counts settle: a viewer who prefers less motion sees them there and still. */
const SETTLED = 40;

/** `?t=30` freezes the studio at that many seconds after it opened, for screenshots and the film. */
const frozenAt = () => {
  const t = new URLSearchParams(window.location.search).get("t");
  return t === null ? null : Number(t);
};

/**
 * Seconds since the studio opened, a tick a second, so the rollout counts grow as rooms behind live reach the
 * goal. Everything shown is a function of this number, so every visit sees the same match.
 */
export function useTick(): number {
  const [t, setT] = useState(() => {
    const frozen = frozenAt();
    if (frozen !== null) return frozen;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? SETTLED : 0;
  });
  useEffect(() => {
    if (frozenAt() !== null || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setT((n) => n + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return t;
}
