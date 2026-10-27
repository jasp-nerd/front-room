import ashvaleCrest from "@frontroom/design/crests/ashvale.svg";
import kestrelCrest from "@frontroom/design/crests/kestrel.svg";
import { goal, scoreText } from "../../../fixtures/goal";
import styles from "./views.module.css";

/** The score as the phone shows it after the goal, between the two crests. */
export function ScoreLine() {
  return (
    <p className={styles.score}>
      <img src={kestrelCrest} alt="" className={styles.crest} />
      <span>Kestrel {scoreText(goal.scoreAfter)} Ashvale</span>
      <img src={ashvaleCrest} alt="" className={styles.crest} />
      <span className={styles.scoreClock}>{goal.goalClock}</span>
    </p>
  );
}
