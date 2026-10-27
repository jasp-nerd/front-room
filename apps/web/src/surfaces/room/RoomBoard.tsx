import { clubs, type Fan } from "../../fixtures/room";
import { agentReason, type RoomFacts, seatOrder, shortTitle, weightOf } from "./facts";
import styles from "./RoomBoard.module.css";

/**
 * The living room drawn top-down like a coach's tactics board: the TV is the goal, the sofa is the
 * back line, and every bid is an arrow from a fan to the overlay their agent wants.
 */

export const BOARD = { width: 1064, height: 904 };
const ROOM = { left: 32, right: 1032, top: 112, bottom: 848 };
const TV = { cx: 532, width: 300, back: 52 };
const CANDIDATE_Y = 392;
const TOKEN_R = 28;
const SEAT_R = 30;
const SOFA = { left: 112, right: 952, top: 512, bottom: 620, arm: 28 };
const SEAT_Y = 560;

interface Point {
  x: number;
  y: number;
}

/** Winner in the middle, straight under the TV; the struck ones either side, in the Director's order. */
function candidatePositions(facts: RoomFacts): Record<string, number> {
  const others = facts.rows.filter((r) => !r.won).map((r) => r.id);
  const sides = [212, 852];
  return Object.fromEntries([
    ...(facts.winner ? [[facts.winner.id, TV.cx] as const] : []),
    ...others.map((id, i) => [id, sides[i % sides.length] ?? TV.cx] as const),
  ]);
}

const seatXs = (count: number) => {
  const inner = SOFA.right - SOFA.left - 2 * SOFA.arm;
  return Array.from({ length: count }, (_, i) => SOFA.left + SOFA.arm + (inner / count) * (i + 0.5));
};

/** A gently curved arrow, like a pass drawn on a tactics board, stopping short of both tokens. */
function arrow(from: Point, to: Point, width: number, startGap: number, endGap: number) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy);
  const ux = dx / length;
  const uy = dy / length;
  const start = { x: from.x + ux * startGap, y: from.y + uy * startGap };
  const tip = { x: to.x - ux * endGap, y: to.y - uy * endGap };
  // Arrows bow away from the middle of the board, so the ones heading left and right fan apart.
  const bend = 0.08 * length * (dx < 0 ? -1 : 1);
  const control = { x: (start.x + tip.x) / 2 - uy * bend, y: (start.y + tip.y) / 2 + ux * bend };

  // The head points along the curve's last tangent, and the line stops where the head begins.
  const tx = tip.x - control.x;
  const ty = tip.y - control.y;
  const tl = Math.hypot(tx, ty);
  const hx = tx / tl;
  const hy = ty / tl;
  const headLength = 12 + width;
  const headHalf = width / 2 + 6;
  const base = { x: tip.x - hx * headLength, y: tip.y - hy * headLength };
  const head = [
    `${tip.x},${tip.y}`,
    `${base.x - hy * headHalf},${base.y + hx * headHalf}`,
    `${base.x + hy * headHalf},${base.y - hx * headHalf}`,
  ].join(" ");
  return { line: `M ${start.x} ${start.y} Q ${control.x} ${control.y} ${base.x} ${base.y}`, head };
}

export function RoomBoard({ facts }: { facts: RoomFacts }) {
  const candidateX = candidatePositions(facts);
  const seated = seatOrder(candidateX, facts.bids);
  const xs = seatXs(seated.length);
  const seatX = Object.fromEntries(seated.map((fan, i) => [fan.id, xs[i] ?? 0]));
  const struckIds = new Set(facts.rows.filter((r) => r.struckBy).map((r) => r.id));
  // Struck bids go underneath, so the bids that counted always read on top.
  const ordered = [...facts.bids].sort(
    (a, b) => Number(struckIds.has(b.candidateId)) - Number(struckIds.has(a.candidateId)),
  );

  return (
    <div className={styles.board} style={{ width: BOARD.width, height: BOARD.height }}>
      <svg
        className={styles.drawing}
        width={BOARD.width}
        height={BOARD.height}
        viewBox={`0 0 ${BOARD.width} ${BOARD.height}`}
        role="img"
        aria-label="The living room from above: four fans on the sofa, their agents' bids, and the overlay that won the TV"
      >
        <Room />
        <TvGoal />
        <Sofa seatXs={xs} />

        {ordered.map((bid) => {
          const weight = weightOf(facts.decision, bid.agentId)?.weight ?? 1;
          const width = 12 * bid.utility * weight;
          const from = { x: seatX[bid.agentId] ?? 0, y: SEAT_Y };
          const to = { x: candidateX[bid.candidateId] ?? 0, y: CANDIDATE_Y };
          const { line, head } = arrow(from, to, width, SEAT_R + 8, TOKEN_R + 6);
          const struck = struckIds.has(bid.candidateId);
          return (
            <g key={`${bid.agentId}-${bid.candidateId}`} className={struck ? styles.bidStruck : styles.bid}>
              <path
                d={line}
                strokeWidth={width}
                strokeDasharray={struck ? `${width * 0.2} ${width * 1.4}` : undefined}
              />
              <polygon points={head} />
            </g>
          );
        })}

        {facts.winner && <WinningPath />}

        {facts.rows.map((row) => (
          <CandidateToken key={row.id} x={candidateX[row.id] ?? 0} won={row.won} />
        ))}
        {seated.map((fan) => (
          <SeatToken key={fan.id} fan={fan} x={seatX[fan.id] ?? 0} dropped={facts.dropped.has(fan.id)} />
        ))}
      </svg>

      <p className={styles.tvLabel} style={{ left: TV.cx + TV.width / 2 + 24, top: TV.back + 6 }}>
        The TV
      </p>

      <Legend />

      {facts.winner && (
        <div className={styles.winnerLabel} style={{ left: TV.cx + 28, top: ROOM.top + 40 }}>
          <p className={styles.winnerTitle}>{facts.winner.title}</p>
          <p className={styles.onTv}>On the TV</p>
        </div>
      )}

      {facts.rows
        .filter((r) => r.struckBy)
        .map((row) => (
          <div
            key={row.id}
            className={styles.struckLabel}
            style={{
              left: (candidateX[row.id] ?? 0) - 170,
              bottom: BOARD.height - CANDIDATE_Y + TOKEN_R + 18,
            }}
          >
            <p className={styles.struckTitle}>{row.title}</p>
            <p className={styles.note}>
              {row.id === facts.mostWanted.id ? "Most wanted, " : ""}
              {row.fairShare}% of the room. Struck.
            </p>
          </div>
        ))}

      {seated.map((fan) => (
        <SeatLabel key={fan.id} fan={fan} x={seatX[fan.id] ?? 0} facts={facts} />
      ))}
    </div>
  );
}

/** How to read the arrows, in the corner of the board where a coach would write it. */
function Legend() {
  return (
    <ul className={styles.legend}>
      <li>
        <svg width="56" height="12" aria-hidden="true">
          <line className={styles.legendCounted} x1="2" y1="6" x2="54" y2="6" />
        </svg>
        A bid that counted
      </li>
      <li>
        <svg width="56" height="12" aria-hidden="true">
          <line className={styles.legendStruck} x1="4" y1="6" x2="54" y2="6" />
        </svg>
        A bid for a pick the rules struck
      </li>
      <li>Thicker: wanted more, or waited longer</li>
    </ul>
  );
}

/** The walls of the room in pencil, open only where the TV sits. */
function Room() {
  const { left, right, top, bottom } = ROOM;
  return (
    <g className={styles.chalk}>
      <path
        d={`M ${TV.cx - TV.width / 2} ${top} H ${left} V ${bottom} H ${right} V ${top} H ${TV.cx + TV.width / 2}`}
      />
    </g>
  );
}

/** The TV as a goal seen from above: posts on the wall line, the net behind it. */
function TvGoal() {
  const left = TV.cx - TV.width / 2;
  const right = TV.cx + TV.width / 2;
  const netLines = Array.from({ length: 14 }, (_, i) => left + ((i + 1) * TV.width) / 15);
  return (
    <g>
      <g className={styles.net}>
        {netLines.map((x) => (
          <line key={`v${x}`} x1={x} y1={TV.back} x2={x} y2={ROOM.top} />
        ))}
        {[0.33, 0.66].map((t) => {
          const y = TV.back + (ROOM.top - TV.back) * t;
          return <line key={`h${t}`} x1={left} y1={y} x2={right} y2={y} />;
        })}
      </g>
      <path className={styles.goal} d={`M ${left} ${ROOM.top} V ${TV.back} H ${right} V ${ROOM.top}`} />
    </g>
  );
}

function Sofa({ seatXs: xs }: { seatXs: number[] }) {
  const { left, right, top, bottom, arm } = SOFA;
  const cushion = (right - left - 2 * arm) / xs.length;
  return (
    <g className={styles.sofa}>
      <rect x={left} y={top} width={right - left} height={bottom - top} rx={10} />
      {xs.map((x) => (
        <rect
          key={x}
          className={styles.cushion}
          x={x - cushion / 2 + 3}
          y={top + 8}
          width={cushion - 6}
          height={bottom - top - 40}
          rx={6}
        />
      ))}
    </g>
  );
}

/** The pick that won, and the single robin line from it into the TV. */
function WinningPath() {
  const { line, head } = arrow({ x: TV.cx, y: CANDIDATE_Y }, { x: TV.cx, y: ROOM.top }, 10, TOKEN_R + 8, 10);
  return (
    <g className={styles.winning}>
      <path d={line} strokeWidth={10} />
      <polygon points={head} />
    </g>
  );
}

function CandidateToken({ x, won }: { x: number; won: boolean }) {
  if (won) {
    return (
      <g>
        <circle className={styles.winnerRing} cx={x} cy={CANDIDATE_Y} r={TOKEN_R + 9} />
        <circle className={styles.winnerToken} cx={x} cy={CANDIDATE_Y} r={TOKEN_R} />
      </g>
    );
  }
  const d = TOKEN_R * 0.45;
  return (
    <g>
      <circle className={styles.struckToken} cx={x} cy={CANDIDATE_Y} r={TOKEN_R} />
      <path
        className={styles.cross}
        d={`M ${x - d} ${CANDIDATE_Y - d} L ${x + d} ${CANDIDATE_Y + d} M ${x + d} ${CANDIDATE_Y - d} L ${x - d} ${CANDIDATE_Y + d}`}
      />
    </g>
  );
}

function SeatToken({ fan, x, dropped }: { fan: Fan; x: number; dropped: boolean }) {
  const club = clubs[fan.club];
  if (dropped) {
    return (
      <g>
        <circle className={styles.seatDropped} cx={x} cy={SEAT_Y} r={SEAT_R} />
        <text className={styles.seatInitial} x={x} y={SEAT_Y + 10} style={{ fill: "var(--ink-muted)" }}>
          {fan.name.charAt(0)}
        </text>
      </g>
    );
  }
  return (
    <g>
      <circle className={styles.seatToken} cx={x} cy={SEAT_Y} r={SEAT_R} style={{ fill: club.colour }} />
      <text className={styles.seatInitial} x={x} y={SEAT_Y + 10} style={{ fill: club.onColour }}>
        {fan.name.charAt(0)}
      </text>
    </g>
  );
}

/** Under each seat: who sits there, what their agent bid and why, and what reached their phone. */
function SeatLabel({ fan, x, facts }: { fan: Fan; x: number; facts: RoomFacts }) {
  const weight = weightOf(facts.decision, fan.id)?.weight ?? 1;
  const delivered = facts.deliveredPrivately.get(fan.id);
  const dropped = facts.dropped.has(fan.id);
  const own = facts.bids.filter((b) => b.agentId === fan.id).sort((a, b) => b.utility - a.utility);
  return (
    <div className={styles.seatLabel} style={{ left: x - 86, top: SOFA.bottom + 16 }}>
      <p className={styles.seatName}>
        {fan.name} <span className={styles.weight}>×{weight.toFixed(2)}</span>
      </p>
      {dropped ? (
        <>
          <p className={styles.late}>Late, skipped</p>
          <p className={styles.reason}>
            No answer within 4 s. {fan.name} keeps the waiting time for the next decision.
          </p>
        </>
      ) : (
        <>
          <dl className={styles.bids}>
            {own.map((b) => (
              <div key={b.candidateId}>
                <dt>{shortTitle(b.candidateId)}</dt>
                <dd>{b.utility.toFixed(2)}</dd>
              </div>
            ))}
          </dl>
          <p className={styles.reason}>{agentReason(fan)}</p>
          {delivered ? (
            <p className={styles.phoneText}>
              <strong>On {fan.name}'s phone</strong> {shortTitle(delivered)}
            </p>
          ) : (
            <p className={styles.phoneText}>
              <strong>{fan.name}'s pick is on the TV</strong>
            </p>
          )}
        </>
      )}
    </div>
  );
}
