import { type CastId, Helper, Pip } from "@frontroom/design";
import spotPhone from "@frontroom/design/illustration/spot-phone.webp";
import spotTv from "@frontroom/design/illustration/spot-tv.webp";
import { candidates, decision, fans } from "../../fixtures/room";
import styles from "./RoomTrace.module.css";

const winner = decision.candidates.find((c) => c.won);
const struck = decision.candidates.filter((c) => c.struckBy).length;

/**
 * The agents at work on the demo goal, as a chain a skimmer can follow and a judge can check: who ran each
 * step (an agent or a rule) and what it produced. Everything comes from the Room Director's real decision.
 */
export function RoomTrace() {
  return (
    <section className={styles.trace} aria-labelledby="trace-title">
      <h2 id="trace-title" className={styles.title}>
        What happened when Okafor scored
      </h2>
      <ol className={styles.chain}>
        <li className={styles.link}>
          <span className={styles.art}>
            {fans.map((fan) => (
              <Helper key={fan.id} id={fan.id as CastId} size={52} />
            ))}
          </span>
          <span className={styles.kind}>4 AI agents, one per fan</span>
          <strong>Every helper asked for the TV</strong>
        </li>
        <li className={styles.link}>
          <span className={styles.art}>
            <Pip pose="whistle" size={60} />
          </span>
          <span className={styles.kind}>Referee agent: fixed rules, over A2A</span>
          <strong>Pip held back {struck} one-sided picks and counted who had waited longest</strong>
        </li>
        <li className={styles.link} data-won>
          <span className={styles.art}>
            <img src={spotTv} alt="" height={56} />
          </span>
          <span className={styles.kind}>The shared TV</span>
          <strong>{winner ? candidates[winner.candidateId]?.title : "The match"}, fair to both clubs</strong>
        </li>
        <li className={styles.link}>
          <span className={styles.art}>
            <img src={spotPhone} alt="" height={56} />
          </span>
          <span className={styles.kind}>Each fan's phone</span>
          <strong>Every other pick went to its own fan, after the TV</strong>
        </li>
      </ol>
    </section>
  );
}
