import { Button } from "@frontroom/design";
import { useState } from "react";
import { goal } from "../../fixtures/goal";
import { Scaled } from "../../ui/Scaled";
import { TvSurface } from "../tv/TvSurface";
import styles from "./LiveCue.module.css";
import { count, percent, plus, rollout, type StudioCue } from "./studio-fixture";

export interface Withdrawal {
  at: string;
  tvs: number;
  phones: number;
}

interface LiveCueProps {
  cue: StudioCue;
  t: number;
  clock: string;
  withdrawn: Withdrawal | null;
  onWithdraw: (w: Withdrawal) => void;
  onFacts: () => void;
  onWhere: () => void;
}

/** The cue on TVs now: the replay as rooms see it, where it landed, and the one control that matters live. */
export function LiveCue({ cue, t, clock, withdrawn, onWithdraw, onFacts, onWhere }: LiveCueProps) {
  const [confirming, setConfirming] = useState(false);
  const r = rollout(t);
  const onAir = cue.facts.filter((f) => f.checkedBy === "feed").length;
  const ready = cue.languages.filter((l) => l.headline).map((l) => l.lang.toUpperCase());
  const fallback = cue.languages.filter((l) => !l.headline).map((l) => l.lang.toUpperCase());
  const bar = [
    { id: "tv", n: r.onTv, label: "On TVs", className: styles.onTv },
    { id: "other", n: r.otherPick, label: "Another pick won", className: styles.other },
    { id: "held", n: r.held, label: "Held for later", className: styles.held },
  ];

  return (
    <section className={styles.card} aria-labelledby="live-cue">
      <figure className={styles.tv} data-withdrawn={withdrawn ? true : undefined}>
        <div aria-hidden="true">
          <Scaled width={1920} height={1080}>
            <TvSurface state="origin" loopReplay overlayThroughout />
          </Scaled>
        </div>
        {withdrawn && <figcaption className={styles.stamp}>Pulled from TVs and phones</figcaption>}
      </figure>

      <div className={styles.info}>
        <p className={styles.kicker}>
          <span className={styles.kind}>{cue.kind}</span>
          {withdrawn ? (
            `Withdrawn at ${withdrawn.at}`
          ) : (
            <>
              <span className={styles.onAir}>On {count(r.onTv)} TVs now</span>
              since {plus(goal.goalClock, 8)}
            </>
          )}
          <span aria-hidden="true">·</span>
          {cue.note}
        </p>
        <h1 id="live-cue" className={styles.title}>
          {cue.title}
        </h1>
        <div className={styles.chips}>
          <button type="button" className={styles.facts} onClick={onFacts}>
            <span aria-hidden="true">✓</span> All {onAir} on-air facts checked
          </button>
          <button type="button" className={styles.langs} onClick={onWhere}>
            <strong>{ready.join(" ")}</strong> ready
            {fallback.length > 0 && (
              <>
                <span aria-hidden="true">·</span>
                {fallback.join(" ")} get English captions
              </>
            )}
          </button>
        </div>
      </div>

      {withdrawn ? (
        <p className={styles.pulled} role="status">
          Pulled from <strong>{count(withdrawn.tvs)} TVs</strong> and{" "}
          <strong>{count(withdrawn.phones)} phones</strong>. Rooms got a short correction.
        </p>
      ) : (
        <div className={styles.outcome}>
          <div
            className={styles.bar}
            role="img"
            aria-label={bar.map((b) => `${b.label}: ${count(b.n)} rooms`).join(", ")}
          >
            {bar.map((b) => (
              <span key={b.id} className={b.className} style={{ flexGrow: b.n }} />
            ))}
          </div>
          <ul className={styles.legend}>
            {bar.map((b) => (
              <li key={b.id}>
                <i className={b.className} />
                {b.label} <strong>{percent(b.n, r.rooms)}%</strong>
              </li>
            ))}
            <li className={styles.phones}>
              <strong>{count(r.phones)}</strong> phones got it too
            </li>
          </ul>
        </div>
      )}

      {!withdrawn &&
        (confirming ? (
          <div className={styles.confirm} role="alertdialog" aria-labelledby="confirm-line">
            <p id="confirm-line">Pull it from every TV and phone? Rooms get a short correction.</p>
            <Button
              onClick={() => {
                setConfirming(false);
                onWithdraw({ at: clock, tvs: r.onTv, phones: r.phones });
              }}
            >
              Yes, pull it
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Keep it on
            </Button>
          </div>
        ) : (
          <div className={styles.actions}>
            <Button variant="secondary" onClick={() => setConfirming(true)}>
              Withdraw (VAR or error)
            </Button>
          </div>
        ))}
    </section>
  );
}
