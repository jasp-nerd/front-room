import { type CastId, Helper } from "@frontroom/design";
import styles from "./views.module.css";

/** The fan's helper robin and a short line: this card came from your helper, not from the TV. */
export function HelperTag({ fan, children }: { fan: CastId; children: string }) {
  return (
    <p className={styles.helperTag}>
      <Helper id={fan} size={44} className={styles.helperBird} />
      {children}
    </p>
  );
}
