import { type CastId, castColour, FanFace, Helper, Pip } from "@frontroom/design";
import { type Fan, fans } from "../../fixtures/room";
import styles from "./Decision.module.css";
import { minutes, type RoomFacts, rules, shortTitle } from "./facts";

/** What each fan's helper asked for most, or nothing if it was late. */
function favourite(facts: RoomFacts, fan: Fan): string | undefined {
  const own = facts.bids.filter((b) => b.agentId === fan.id);
  return own.reduce<(typeof own)[number] | undefined>(
    (best, b) => (!best || b.utility > best.utility ? b : best),
    undefined,
  )?.candidateId;
}

const tone = (fan: Fan) =>
  ({
    "--fan": `var(--${castColour[fan.id as CastId]})`,
    "--fan-wash": `var(--${castColour[fan.id as CastId]}-wash)`,
  }) as React.CSSProperties;

/**
 * The room's decision in three steps a skimmer can follow: everyone's helper asks, Pip checks the house
 * rules, and the TV gets one pick while everyone else gets theirs on their phone.
 */
export function Decision({ facts }: { facts: RoomFacts }) {
  const { winner, rows, decision, dropped } = facts;
  const struck = rows.filter((r) => r.struckBy);
  const longest = [...decision.weights]
    .filter((w) => !dropped.has(w.agentId))
    .sort((a, b) => b.secondsWithoutScreen - a.secondsWithoutScreen)[0];
  const longestFan = fans.find((f) => f.id === longest?.agentId);

  return (
    <section className={styles.decision} aria-labelledby="decision-title">
      <div className={styles.intro}>
        <h1 id="decision-title" className={styles.title}>
          {winner ? `${winner.title} won the TV` : "The TV stays on the match"}
        </h1>
        {winner && (
          <p className={styles.lead}>
            {winner.askedBy.length} of {fans.length} asked for it, and it's fair to both clubs.
          </p>
        )}
      </div>

      <ol className={styles.steps}>
        <li className={styles.step}>
          <h2 className={styles.stepTitle}>
            <span className={styles.number}>1</span> Every helper asks
          </h2>
          <ul className={styles.fans}>
            {fans.map((fan) => {
              const late = dropped.has(fan.id);
              const pick = favourite(facts, fan);
              return (
                <li key={fan.id} className={styles.fan} style={tone(fan)} data-late={late || undefined}>
                  <FanFace id={fan.id as CastId} size={72} className={styles.face} />
                  <div className={styles.ask}>
                    <p className={styles.name}>{fan.name}</p>
                    {late ? (
                      <p className={styles.pick}>Helper was late, skipped</p>
                    ) : (
                      <p className={styles.pick}>{pick ? shortTitle(pick) : "Nothing"}</p>
                    )}
                    {/* Helpers can ask for more than one thing; the headline counts every ask for the winner. */}
                    {!late && winner && pick !== winner.id && winner.askedBy.includes(fan.id) && (
                      <p className={styles.also}>Also asked for {shortTitle(winner.id)}</p>
                    )}
                  </div>
                  <Helper id={fan.id as CastId} size={56} className={styles.helper} />
                </li>
              );
            })}
          </ul>
        </li>

        <li className={`${styles.step} ${styles.referee}`}>
          <h2 className={styles.stepTitle}>
            <span className={styles.number}>2</span> Pip checks the rules
          </h2>
          <ul className={styles.rules}>
            {struck.map((row) => (
              <li key={row.id} className={styles.rule}>
                <span className={styles.mark} data-kind="no" aria-hidden="true">
                  ✕
                </span>
                <span>
                  <strong>{shortTitle(row.id)}</strong>
                  {row.struckBy && rules[row.struckBy].short}
                </span>
              </li>
            ))}
            {longestFan && longest && (
              <li className={styles.rule}>
                <span className={styles.mark} data-kind="wait" aria-hidden="true">
                  +
                </span>
                <span>
                  <strong>{longestFan.name} has waited longest</strong>
                  {minutes(longest.secondsWithoutScreen)} without a pick, so counts a bit more
                </span>
              </li>
            )}
          </ul>
          <Pip pose="whistle" size={168} className={styles.pip} />
        </li>

        <li className={styles.step}>
          <h2 className={styles.stepTitle}>
            <span className={styles.number}>3</span> One pick on the TV
          </h2>
          {winner && (
            <div className={styles.tv}>
              <span className={styles.onTv}>On the TV</span>
              <p className={styles.tvTitle}>{winner.title}</p>
            </div>
          )}
          <p className={styles.phonesTitle}>The rest go to their phones</p>
          <ul className={styles.phones}>
            {fans.map((fan) => {
              const sent = facts.deliveredPrivately.get(fan.id);
              const late = dropped.has(fan.id);
              return (
                <li key={fan.id} className={styles.phone} style={tone(fan)} data-late={late || undefined}>
                  <FanFace id={fan.id as CastId} size={36} className={styles.phoneFace} />
                  <span className={styles.phoneName}>{fan.name}</span>
                  <span className={styles.phonePick}>
                    {late
                      ? "Keeps their place for next time"
                      : sent
                        ? shortTitle(sent)
                        : "Their pick is on the TV"}
                  </span>
                </li>
              );
            })}
          </ul>
        </li>
      </ol>
    </section>
  );
}
