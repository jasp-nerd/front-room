import { useId, useState } from "react";
import styles from "./Switch.module.css";

interface SwitchProps {
  label: string;
  hint?: string;
  defaultOn?: boolean;
}

/** A settings row with a real switch: a 44px target, labelled, and announced as on or off. */
export function Switch({ label, hint, defaultOn = false }: SwitchProps) {
  const [on, setOn] = useState(defaultOn);
  const id = useId();
  return (
    <div className={styles.row}>
      <div className={styles.text}>
        <span id={id} className={styles.label}>
          {label}
        </span>
        {hint && <span className={styles.hint}>{hint}</span>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-labelledby={id}
        className={styles.switch}
        onClick={() => setOn(!on)}
      >
        <span className={styles.knob} />
      </button>
    </div>
  );
}
