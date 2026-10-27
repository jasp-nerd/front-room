import styles from "./ScoreBug.module.css";

interface Side {
  short: string;
  /** Club colour behind the name, and the ink that reads on it. */
  colour: string;
  ink: string;
  goals: number;
}

/** The broadcaster's score bug, part of the feed itself. Front Room never draws over it or replaces it. */
export function ScoreBug({ home, away, clock }: { home: Side; away: Side; clock: string }) {
  return (
    <section
      className={styles.bug}
      aria-label={`${home.short} ${home.goals}, ${away.short} ${away.goals}, ${clock}`}
    >
      <span className={styles.team} style={{ background: home.colour, color: home.ink }}>
        {home.short}
      </span>
      <span className={styles.score}>
        <span>{home.goals}</span>
        <span className={styles.dash}>–</span>
        <span>{away.goals}</span>
      </span>
      <span className={styles.team} style={{ background: away.colour, color: away.ink }}>
        {away.short}
      </span>
      <span className={styles.clock}>{clock}</span>
    </section>
  );
}
