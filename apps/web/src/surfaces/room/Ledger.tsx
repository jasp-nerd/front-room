import { fanById } from "../../fixtures/room";
import { minutes, type RoomFacts, rules } from "./facts";
import styles from "./Ledger.module.css";

/** The Director's ledger entry for one decision: every pick's support, raw and with waiting, and the waits. */
export function Ledger({ facts }: { facts: RoomFacts }) {
  const { rows, decision } = facts;
  const longestWait = [...decision.weights].sort(
    (a, b) => b.secondsWithoutScreen - a.secondsWithoutScreen,
  )[0];
  const longestSeconds = longestWait?.secondsWithoutScreen || 1;

  return (
    <section className={styles.ledger} aria-label="The Director's ledger">
      <div className={styles.block}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Pick</th>
              <th scope="col" className={styles.num}>
                Asked
              </th>
              <th scope="col" className={styles.num}>
                Raw
              </th>
              <th scope="col" className={styles.num}>
                With waiting
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className={row.won ? styles.won : undefined}>
                <th scope="row">
                  <span className={styles.overlay}>{row.title}</span>
                  <span className={styles.outcome}>
                    {row.won ? "On the TV" : row.struckBy ? rules[row.struckBy].short : "Lost on support"}
                  </span>
                </th>
                <td className={styles.num}>{row.askedBy.length}</td>
                <td className={styles.num}>{row.rawShare}%</td>
                <td className={styles.num}>{row.fairShare}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className={styles.note}>
          Shares add up how much each helper wanted a pick, not just how many asked.
        </p>
      </div>

      <div className={styles.block}>
        <h2 className={styles.heading}>Waiting counts</h2>
        {longestWait && (
          <p className={styles.body}>
            {fanById(longestWait.agentId).name} has gone {minutes(longestWait.secondsWithoutScreen)} without a
            pick on the TV, so counts ×{longestWait.weight.toFixed(2)}.
          </p>
        )}
        <ul className={styles.weights}>
          {decision.weights.map((w) => (
            <li key={w.agentId}>
              <span className={styles.who}>{fanById(w.agentId).name}</span>
              <span className={styles.bar} aria-hidden="true">
                <span style={{ width: `${(w.secondsWithoutScreen / longestSeconds) * 100}%` }} />
              </span>
              <span className={styles.waited}>{Math.round(w.secondsWithoutScreen / 60)} min</span>
              <span className={styles.factor}>×{w.weight.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className={styles.footnote}>
        Same bids, same result: every decision can be replayed. This one took{" "}
        {decision.decidedInMs.toFixed(2)} ms.
      </p>
    </section>
  );
}
