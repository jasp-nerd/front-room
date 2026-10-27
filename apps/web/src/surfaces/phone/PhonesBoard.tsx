import { type CastId, castColour, FanFace } from "@frontroom/design";
import type { CSSProperties } from "react";
import { type Depth, fans } from "../../fixtures/room";
import { FanPhone } from "./PhoneSurface";
import styles from "./PhoneSurface.module.css";

/** How each fan likes to watch, in a few words. */
const watches: Record<Depth, string> = {
  analyst: "Wants the numbers",
  casual: "Simple, in Spanish",
  kid: "Ten, loves goals",
  audio: "Would rather listen",
};

/** What each phone shows for Okafor's goal (the demo room's decision), in plain words. */
const got: Record<string, string> = {
  rob: "Kestrel's pressing map, with the numbers",
  ana: "How Ashvale's keeper saw it, in Spanish",
  leo: "His pick made the TV, so he gets a quiz",
  sam: "The goal read aloud, in big text",
};

/** The board's size for each layout, as laid out before scaling. */
export const boardSize = {
  4: { width: 1920, height: 1010 },
  2: { width: 960, height: 1960 },
} as const;

/** The four fans' phones for the same goal, each on a field in that fan's colour. */
export function PhonesBoard({ columns = 4 }: { columns?: 2 | 4 }) {
  const { width, height } = boardSize[columns];
  const size = { "--columns": columns, "--board-width": `${width}px`, "--board-height": `${height}px` };
  return (
    <ul className={styles.board} style={size as CSSProperties}>
      {fans.map((fan) => (
        <li key={fan.id} className={styles.figure} data-colour={castColour[fan.id as CastId]}>
          <div className={styles.who}>
            <span className={styles.face}>
              <FanFace id={fan.id as CastId} size={84} />
            </span>
            <span>
              <strong className={styles.name}>{fan.name}</strong>
              <span className={styles.watches}>{watches[fan.depth]}</span>
            </span>
          </div>
          <div className={styles.device}>
            <FanPhone fan={fan} />
          </div>
          <p className={styles.outcome}>{got[fan.id]}</p>
        </li>
      ))}
    </ul>
  );
}
