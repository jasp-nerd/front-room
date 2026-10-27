import { Pip } from "../Pip/Pip";
import { ProvenanceTokens } from "../ProvenanceTokens/ProvenanceTokens";
import styles from "./LowerThird.module.css";

interface LowerThirdProps {
  headline: string;
  line: string;
  /** How the room decided: how many asked, out of how many. Never who. */
  asked: number;
  inRoom: number;
  neutral: boolean;
  /** Households can switch the provenance line off; the overlay then carries only the story. */
  showProvenance?: boolean;
}

/** The one overlay Front Room puts on the shared screen, chosen by the room. */
export function LowerThird({
  headline,
  line,
  asked,
  inRoom,
  neutral,
  showProvenance = true,
}: LowerThirdProps) {
  return (
    <section className={styles.plate} aria-live="polite">
      <div className={styles.main}>
        <h2 className={styles.headline}>{headline}</h2>
        <p className={styles.line}>{line}</p>
      </div>
      {showProvenance && (
        <div className={styles.provenance}>
          <ProvenanceTokens asked={asked} inRoom={inRoom} />
          <span className={styles.why}>
            {asked} of {inRoom} in the room asked for this
            {neutral && <span className={styles.neutral}>Kept neutral: both clubs are here</span>}
          </span>
          <Pip pose="whistle" size={112} alt="Pip, the room's referee" className={styles.maker} />
        </div>
      )}
    </section>
  );
}
