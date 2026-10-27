import styles from "./MatchLane.module.css";
import { asksPerMinute, earlierCues, moments, type StudioCue, stateLabel } from "./studio-fixture";

interface MatchLaneProps {
  cues: StudioCue[];
  minute: number;
}

/** The match along one line: the cues, what's on and what's next, over how much rooms asked, minute by minute. */
export function MatchLane({ cues, minute }: MatchLaneProps) {
  const asks = asksPerMinute(minute);
  const most = Math.max(...asks.map((a) => a ?? 0));
  const latest = moments[moments.length - 1];
  return (
    <section className={styles.lane} aria-labelledby="lane">
      <h2 id="lane" className={styles.title}>
        Cues
      </h2>
      <ol className={styles.cues}>
        <li className={styles.earlier} title={earlierCues.map((c) => `${c.minute} ${c.title}`).join("\n")}>
          <span className={styles.state} data-state="done">
            Done
          </span>
          <strong>{earlierCues.length} earlier cues</strong>
          <span className={styles.note}>
            From {earlierCues[0]?.minute} to {earlierCues[earlierCues.length - 1]?.minute}
          </span>
        </li>
        {cues.map((cue) => (
          <li key={cue.id} className={styles.cue} data-state={cue.state}>
            <span className={styles.state} data-state={cue.state}>
              {stateLabel[cue.state]}
            </span>
            <span className={styles.minute}>{cue.minute}</span>
            <strong className={styles.cueTitle}>{cue.title}</strong>
            <span className={styles.note}>{cue.note}</span>
          </li>
        ))}
      </ol>

      <div className={styles.strip}>
        <p className={styles.stripLabel}>Asks per minute, all match</p>
        <div
          className={styles.bars}
          role="img"
          aria-label={`Asks per minute. They jump after every goal; the biggest jump is after ${latest?.label}.`}
        >
          {asks.map((a, i) => (
            <span
              // biome-ignore lint/suspicious/noArrayIndexKey: one bar per match minute, in order
              key={i}
              className={styles.minuteBar}
              data-future={a === null || undefined}
              data-now={i + 1 === minute || undefined}
              style={{ height: `${Math.max(6, ((a ?? 0) / most) * 100)}%` }}
            />
          ))}
          <span className={styles.half} style={{ left: "50%" }} aria-hidden="true" />
        </div>
        <div className={styles.moments} aria-hidden="true">
          {moments.map((m) => (
            <span
              key={m.minute}
              className={styles.moment}
              data-latest={m === latest || undefined}
              style={{ left: `${((m.minute - 0.5) / 90) * 100}%` }}
              title={`${m.minute}' ${m.label}`}
            >
              {m === latest ? `${m.minute}' ${m.label}` : ""}
            </span>
          ))}
        </div>
        <p className={styles.axis} aria-hidden="true">
          <span>0'</span>
          <span>Half time</span>
          <span>90'</span>
        </p>
      </div>
    </section>
  );
}
