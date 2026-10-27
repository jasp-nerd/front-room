import type { ReactNode } from "react";
import styles from "./Chip.module.css";

/** Where a cue is on its way to the rooms, from first draft to finished. */
export type ChipState = "drafted" | "checked" | "armed" | "on-tvs" | "done";

const stateClass: Record<ChipState, string | undefined> = {
  drafted: styles.quiet,
  checked: styles.checked,
  armed: styles.armed,
  "on-tvs": styles.onTvs,
  done: styles.quiet,
};

/**
 * One chip for every state: same shape and size, louder as a cue gets closer to the rooms.
 * Only "on TVs" is robin, because that is what the rooms share.
 */
export function Chip({ state, children }: { state: ChipState; children: ReactNode }) {
  return <span className={`${styles.chip} ${stateClass[state] ?? ""}`}>{children}</span>;
}
