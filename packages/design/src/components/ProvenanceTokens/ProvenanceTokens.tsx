import styles from "./ProvenanceTokens.module.css";

interface ProvenanceTokensProps {
  /** How many in the room asked for what is on screen. */
  asked: number;
  inRoom: number;
  /** `tv` for a 1080p frame, `phone` for a 390px screen. */
  size?: "tv" | "phone";
}

/**
 * How the room decided, as anonymous dots: one per fan, robin for those who asked. Never names or clubs:
 * the shared screen shows how many, not who.
 */
export function ProvenanceTokens({ asked, inRoom, size = "tv" }: ProvenanceTokensProps) {
  return (
    <span className={`${styles.tokens} ${styles[size]}`} aria-hidden="true">
      {Array.from({ length: inRoom }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: tokens are anonymous and fixed in number.
        <span key={i} className={i < asked ? styles.asked : styles.token} />
      ))}
    </span>
  );
}
