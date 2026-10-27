import styles from "./Captions.module.css";

export interface CaptionLine {
  lang: string;
  text: string;
}

/** Captions for everyone in the room, one line per language present. Never displaced by an overlay. */
export function Captions({ lines }: { lines: CaptionLine[] }) {
  return (
    <div className={styles.captions}>
      {lines.map((line) => (
        <p key={line.lang} lang={line.lang} className={styles.line}>
          {line.text}
        </p>
      ))}
    </div>
  );
}
