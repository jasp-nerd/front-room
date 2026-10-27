import type { CastId } from "@frontroom/design";
import type { Fan } from "../../../fixtures/room";
import { myNumber, playerByLabel, playerFocus } from "../../../fixtures/stats";
import { copy } from "../copy";
import { HelperTag } from "./HelperTag";
import styles from "./PlayerFocus.module.css";
import { ScoreLine } from "./ScoreLine";

/**
 * Above every lens: the player this fan follows and their part in the moment, and the one number they asked
 * to keep in view. Nothing shows for a fan who follows nobody and named no number.
 */
export function FocusBar({ fan }: { fan: Fan }) {
  const words = copy[fan.lang];
  const followed = fan.follows?.[0];
  const focus = followed ? playerFocus(followed, fan.lang) : undefined;
  const number = myNumber(fan);
  if (!focus && !number) return null;
  return (
    <section className={styles.bar} aria-label={words.myNumber}>
      {focus && (
        <p className={styles.focus}>
          <span className={styles.label}>
            {words.following} {focus.name}
          </span>
          {focus.line}
        </p>
      )}
      {number && (
        <p className={styles.number}>
          <span className={styles.label}>{words.myNumber}</span>
          <span>
            {number.name}, {number.whose} <strong>{number.value}</strong>
          </span>
        </p>
      )}
    </section>
  );
}

/** When the room sends a fan a player card instead of the TV's pick: that player's night, in big numbers. */
export function PlayerCardView({ fan, card }: { fan: Fan; card: string }) {
  const spanish = fan.lang === "es";
  const player = playerByLabel(card.replace(/^player-/, "").replace(/^./, (c) => c.toUpperCase()));
  if (!player) return null;
  const decimal = (n: number) => n.toLocaleString(spanish ? "es" : "en-GB");
  const tiles = [
    [spanish ? "km esta noche" : "km tonight", decimal(player.distanceKm)],
    [spanish ? "km/h máxima" : "km/h top speed", decimal(player.topSpeedKmh)],
    ["sprints", String(player.sprints)],
    [spanish ? "tiros a puerta" : "shots on target", String(player.shotsOnTarget)],
  ];
  return (
    <div className={styles.card}>
      <ScoreLine />
      <HelperTag fan={fan.id as CastId}>
        {spanish ? "Tu ayudante te mandó esto" : "Your helper sent this instead"}
      </HelperTag>
      <h2 className={styles.headline}>
        {player.name} {spanish ? "en cifras" : "in numbers"}
      </h2>
      {player.inTheMove && (
        <p className={styles.move}>
          {spanish
            ? `${player.inTheMove.metres} m corridos en la jugada del gol, hasta ${decimal(player.inTheMove.topSpeedKmh)} km/h.`
            : `${player.inTheMove.metres} m run in the goal's move, up to ${decimal(player.inTheMove.topSpeedKmh)} km/h.`}
        </p>
      )}
      <dl className={styles.tiles}>
        {tiles.map(([what, value]) => (
          <div key={what}>
            <dt>{what}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <p className={styles.note}>
        {spanish
          ? "Medido con el seguimiento del partido, hasta el 61:41."
          : "Measured from the match tracking, up to 61:41."}
      </p>
    </div>
  );
}
