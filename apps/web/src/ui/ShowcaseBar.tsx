import { Wordmark } from "@frontroom/design";
import styles from "./FitStage.module.css";

interface ShowcaseBarProps {
  /** What the visitor is looking at, in one sentence. */
  line: string;
  /** Where to go from here to see it for real. */
  action?: { href: string; label: string };
}

/** The bar over a showcase page (/phones, /tv): this is an example screen, and here's the way back. */
export function ShowcaseBar({ line, action }: ShowcaseBarProps) {
  return (
    <>
      <a href="/" aria-label="Front Room, home" className={styles.home}>
        <Wordmark variant="lockup" height={22} />
      </a>
      <p className={styles.line}>{line}</p>
      {action && (
        <a className={styles.action} href={action.href}>
          {action.label}
        </a>
      )}
    </>
  );
}
