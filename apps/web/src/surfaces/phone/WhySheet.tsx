import { Button } from "@frontroom/design";
import { askedForWinner, decision, fans } from "../../fixtures/room";
import styles from "./WhySheet.module.css";

/** Where things sit in the little room diagram, in its own 326 × 196 units. */
const TV = { x: 163, y: 20 };
const WINNER = { x: 133, y: 74 };
const STRUCK = { x: 266, y: 74 };
const SEAT_Y = 158;

/**
 * "Why this?": the room's decision drawn small, without naming anyone. The fan sees their own seat as "You";
 * everyone else is an anonymous disc, lit if they asked for what is on the TV.
 */
function RoomDiagram({ fanId, winnerTitle }: { fanId: string; winnerTitle: string }) {
  const asked = new Set(askedForWinner());
  const others = fans.filter((f) => f.id !== fanId);
  const seats = [...others, ...fans.filter((f) => f.id === fanId)].map((fan, i) => ({
    x: 46 + i * 74,
    you: fan.id === fanId,
    asked: asked.has(fan.id),
  }));
  return (
    <svg className={styles.diagram} viewBox="0 0 326 196" role="img" aria-label="How the room decided">
      <rect x={TV.x - 44} y={4} width={88} height={32} rx={8} className={styles.tv} />
      <text x={TV.x} y={25} className={styles.tvLabel}>
        TV
      </text>
      <line x1={WINNER.x} y1={WINNER.y - 15} x2={TV.x - 10} y2={40} className={styles.toTv} />
      {seats.map((seat) =>
        seat.asked ? (
          <line
            key={seat.x}
            x1={seat.x}
            y1={SEAT_Y - 14}
            x2={WINNER.x}
            y2={WINNER.y + 15}
            className={styles.bid}
          />
        ) : (
          <line
            key={seat.x}
            x1={seat.x}
            y1={SEAT_Y - 14}
            x2={STRUCK.x}
            y2={STRUCK.y + 15}
            className={styles.lost}
          />
        ),
      )}
      <rect x={WINNER.x - 82} y={WINNER.y - 15} width={164} height={30} rx={15} className={styles.winner} />
      <text x={WINNER.x} y={WINNER.y + 5} className={styles.winnerLabel}>
        {winnerTitle}
      </text>
      <rect x={STRUCK.x - 48} y={STRUCK.y - 15} width={96} height={30} rx={15} className={styles.struck} />
      <text x={STRUCK.x} y={STRUCK.y + 5} className={styles.struckLabel}>
        Most wanted
      </text>
      <line x1={STRUCK.x - 38} y1={STRUCK.y} x2={STRUCK.x + 38} y2={STRUCK.y} className={styles.strike} />
      <text x={STRUCK.x} y={STRUCK.y - 22} className={styles.rule}>
        Favours one club
      </text>
      {seats.map((seat) => (
        <g key={seat.x}>
          <circle cx={seat.x} cy={SEAT_Y} r={12} className={seat.asked ? styles.seatAsked : styles.seat} />
          {seat.you && (
            <text x={seat.x} y={SEAT_Y + 30} className={styles.you}>
              You
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

export function WhySheet({
  fanId,
  winnerTitle,
  yourPick,
  onClose,
}: {
  fanId: string;
  winnerTitle: string;
  yourPick: string;
  onClose?: () => void;
}) {
  const asked = askedForWinner().length;
  const struck = decision.candidates.some((c) => c.struckBy === "neutral-framing");
  return (
    <div className={styles.scrim}>
      <section className={styles.sheet} aria-labelledby="why-title">
        <span className={styles.handle} aria-hidden="true" />
        <h2 id="why-title" className={styles.title}>
          Why this is on the TV
        </h2>
        <RoomDiagram fanId={fanId} winnerTitle={winnerTitle} />
        <p>
          {asked} of {fans.length} in the room asked for it.
          {struck && " The most-wanted pick favours one club, so Pip sent it to phones instead."}
        </p>
        <p className={styles.yours}>
          <span>Your pick</span>
          <strong>{yourPick}</strong>
          <span className={styles.where}>On your phone</span>
        </p>
        <p className={styles.small}>
          Same asks, same result, every time. Pip saw what your helper asked for, never what you told it.
        </p>
        <Button block onClick={onClose}>
          Got it
        </Button>
      </section>
    </div>
  );
}
