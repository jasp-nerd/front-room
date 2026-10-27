import styles from "./LensStrip.module.css";

interface LensStripProps {
  label: string;
  onTv: string;
  /** How far behind live the TV is, in seconds. */
  behind: number;
  /** The same, as a sentence for screen readers. */
  sync: string;
  why: string;
  onWhy?: () => void;
}

/** Always at the top of the phone, on one line: what the shared TV shows now, how in step we are, and why. */
export function LensStrip({ label, onTv, behind, sync, why, onWhy }: LensStripProps) {
  return (
    <section className={styles.strip} aria-label={label}>
      <span className={styles.shared} aria-hidden="true" />
      <p className={styles.now}>
        <span className={styles.label}>{label}</span> {onTv}
      </p>
      <span className={styles.sync} title={sync} role="img" aria-label={sync}>
        −{behind} s
      </span>
      <button type="button" className={styles.why} onClick={onWhy}>
        {why}
      </button>
    </section>
  );
}
