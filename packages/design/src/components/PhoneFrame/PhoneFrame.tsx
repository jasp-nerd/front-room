import type { CSSProperties, ReactNode } from "react";
import type { CastColour } from "../Cast/Cast";
import styles from "./PhoneFrame.module.css";

interface PhoneFrameProps {
  /** Local time on the status bar. */
  time: string;
  lang: string;
  /** Larger type for fans who asked for it. */
  large?: boolean;
  /**
   * The fan's colour. The screen exposes it as `--accent` and `--accent-wash` for chips, bars and fields,
   * so each phone in the room is recognisably its owner's. Robin stays for what the room shares.
   */
  accent?: CastColour;
  children: ReactNode;
}

/** A 390 × 844 phone, drawn plainly so the screen is what you look at. */
export function PhoneFrame({ time, lang, large = false, accent, children }: PhoneFrameProps) {
  const colours = accent
    ? ({ "--accent": `var(--${accent})`, "--accent-wash": `var(--${accent}-wash)` } as CSSProperties)
    : undefined;
  return (
    <div className={styles.device}>
      <div className={styles.screen} lang={lang} data-large={large || undefined} style={colours}>
        <div className={styles.status} aria-hidden="true">
          <span>{time}</span>
        </div>
        {children}
      </div>
    </div>
  );
}
