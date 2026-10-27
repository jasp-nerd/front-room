import { Button, Pip } from "@frontroom/design";
import styles from "./DemandRace.module.css";
import { type Answer, count, type Demand } from "./studio-fixture";

const answerLabel: Record<Answer, string> = {
  "on-tvs": "On TVs",
  armed: "Armed",
  checked: "Checked",
  drafted: "Drafted",
  withdrawn: "Withdrawn",
  none: "No cue yet",
};

export interface Suggestion {
  title: string;
  rooms: number;
  at: string;
}

interface DemandRaceProps {
  demand: Demand[];
  suggestion: Suggestion | null;
  onSuggest: (top: Demand) => void;
  onMake: (item: Demand) => void;
}

const ROW = 40;

/**
 * What rooms want right now, as a bar race: every helper's ask, counted by room and never by fan. Asks the
 * studio has no cue for stand out, and the top ask can go to the gallery for viewers who have no helper.
 */
export function DemandRace({ demand, suggestion, onSuggest, onMake }: DemandRaceProps) {
  const largest = Math.max(...demand.map((d) => d.asks));
  // Rows keep their place in the DOM and move by rank, so the race reorders smoothly.
  const byId = [...demand].sort((a, b) => a.id.localeCompare(b.id));
  const rank = new Map(demand.map((d, i) => [d.id, i]));
  const unmet = demand.find((d) => d.answer === "none");
  const drafted = demand.find((d) => d.answer === "drafted");
  const forGallery = demand.find((d) => d.answer !== "on-tvs" && d.answer !== "withdrawn");

  return (
    <section className={styles.panel} aria-labelledby="demand">
      <header className={styles.head}>
        <div>
          <h2 id="demand" className={styles.title}>
            What rooms want right now
          </h2>
          <p className={styles.sub}>Rooms whose helpers asked for it, last two minutes</p>
        </div>
      </header>

      <ol className={styles.race} style={{ height: demand.length * ROW }}>
        {byId.map((d) => (
          <li
            key={d.id}
            className={styles.row}
            data-answer={d.answer}
            style={{ transform: `translateY(${(rank.get(d.id) ?? 0) * ROW}px)` }}
          >
            <span className={styles.what}>
              <span className={styles.name}>{d.title}</span>
              <span className={styles.tag}>{answerLabel[d.answer]}</span>
            </span>
            <span className={styles.track} aria-hidden="true">
              <span className={styles.fill} style={{ width: `${(d.asks / largest) * 100}%` }} />
            </span>
            <span className={styles.n}>{count(d.asks)}</span>
          </li>
        ))}
      </ol>

      <div className={styles.cards}>
        {drafted ? (
          <div className={styles.unmet} data-done>
            <p className={styles.unmetLine}>
              <strong>"{drafted.title}"</strong> is drafted. It's in the cues below, waiting for a check.
            </p>
          </div>
        ) : (
          unmet && (
            <div className={styles.unmet}>
              <p className={styles.big}>{count(unmet.asks)}</p>
              <p className={styles.unmetLine}>
                rooms asked <strong>"{unmet.title}"</strong> There's no cue for it yet.
              </p>
              <Button onClick={() => onMake(unmet)}>Clip it</Button>
            </div>
          )
        )}

        <div className={styles.gallery} data-sent={suggestion ? true : undefined}>
          <Pip pose="remote" size={52} />
          {suggestion ? (
            <p className={styles.galleryLine} role="status">
              <strong>Sent to the gallery at {suggestion.at}:</strong> {suggestion.title}. The main feed can
              show it to viewers without a helper.
            </p>
          ) : (
            <p className={styles.galleryLine}>
              Viewers without a helper only see the main feed. Tell the gallery what rooms want.
            </p>
          )}
          {forGallery && !suggestion && (
            <Button variant="secondary" onClick={() => onSuggest(forGallery)}>
              Suggest to gallery
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}
