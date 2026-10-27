import { Wordmark } from "@frontroom/design";
import ashvale from "@frontroom/design/crests/ashvale.svg";
import kestrel from "@frontroom/design/crests/kestrel.svg";
import { goal, scoreText } from "../../fixtures/goal";
import { clubs } from "../../fixtures/room";
import { useDecision } from "../../live/feed";
import { Decision } from "./Decision";
import { droppedFromUrl, roomFacts } from "./facts";
import { Ledger } from "./Ledger";
import { RoomBoard } from "./RoomBoard";
import styles from "./RoomSurface.module.css";

/**
 * How the room decided what goes on the TV: the decision in three plain steps, and behind "Show the
 * numbers", the bids drawn as a tactics board and the Director's ledger.
 * `?dropped=sam` shows how the room decides when a helper misses the deadline.
 */
export function RoomSurface() {
  const live = useDecision("room");
  // A live decision already left out any agent that missed the deadline, so it is shown, not recomputed.
  const facts = live.dropped.length
    ? { ...roomFacts(live.bids, live.decision), dropped: new Set(live.dropped) }
    : roomFacts(live.bids, live.decision, droppedFromUrl());
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <a href="/" className={styles.home}>
          <Wordmark variant="lockup" height={24} />
        </a>
        <p className={styles.match}>
          <img className={styles.crest} src={kestrel} alt="" />
          <span className={styles.team}>{clubs.kestrel.short}</span>
          <span className={styles.score}>{scoreText(goal.scoreAfter)}</span>
          <span className={styles.team}>{clubs.ashvale.short}</span>
          <img className={styles.crest} src={ashvale} alt="" />
          <span className={styles.clock}>{goal.goalClock}</span>
        </p>
      </header>

      <Decision facts={facts} />

      <details className={styles.numbers}>
        <summary className={styles.summary}>Show the numbers</summary>
        <div className={styles.numbersBody}>
          <div className={styles.boardWrap}>
            <RoomBoard facts={facts} />
          </div>
          <Ledger facts={facts} />
        </div>
      </details>

      <p className={styles.provenance}>
        A made-up league: the clubs, players and match are synthetic. Helpers' asks are shown here with the
        household's consent; phones never see each other's.
      </p>
    </main>
  );
}
