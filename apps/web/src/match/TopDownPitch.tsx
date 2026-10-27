import type { PitchPoint, TrackingFrame } from "@frontroom/protocol";
import type { ReactNode } from "react";
import { PITCH_WIDTH, pitchMarkings } from "./pitch";
import type { PlayerLook } from "./render";
import styles from "./TopDownPitch.module.css";

/**
 * The match drawn from above as chalk on a dark board: the view for phones, slides and the room.
 * Pitch metres in, SVG units out (1 unit = 1 m). The near touchline (y = 0) sits at the bottom.
 */

export interface Arrow {
  from: PitchPoint;
  to: PitchPoint;
  kind: "pass" | "run" | "press";
  /** Any CSS colour; defaults to chalk. */
  colour?: string;
}

export interface Crop {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

interface TopDownPitchProps {
  frame: TrackingFrame;
  players: Record<string, PlayerLook>;
  kits: Record<"home" | "away", { fill: string; ink: string }>;
  arrows?: Arrow[];
  /** Players to draw at full strength; everyone else is dimmed. Omit to draw everyone equally. */
  focus?: string[];
  crop?: Crop;
  title: string;
  children?: ReactNode;
}

const flip = (p: PitchPoint) => ({ x: p.x, y: PITCH_WIDTH - p.y });

export function TopDownPitch({
  frame,
  players,
  kits,
  arrows = [],
  focus,
  crop,
  title,
  children,
}: TopDownPitchProps) {
  const view = crop ?? { x0: -2, x1: 107, y0: -2, y1: 70 };
  const viewBox = `${view.x0} ${PITCH_WIDTH - view.y1} ${view.x1 - view.x0} ${view.y1 - view.y0}`;
  const ball = flip(frame.ball);

  return (
    <svg className={styles.pitch} viewBox={viewBox} role="img" aria-label={title}>
      <defs>
        <marker
          id="td-head"
          viewBox="0 0 10 10"
          refX="7"
          refY="5"
          markerWidth="4"
          markerHeight="4"
          orient="auto"
        >
          <path d="M0 1 L9 5 L0 9 Z" fill="context-stroke" />
        </marker>
      </defs>
      <rect x={-6} y={-6} width={117} height={80} className={styles.board} />
      {pitchMarkings().map((line, i) => (
        <polyline
          // biome-ignore lint/suspicious/noArrayIndexKey: the markings are a fixed list.
          key={i}
          points={line.map((p) => `${p.x},${PITCH_WIDTH - p.y}`).join(" ")}
          className={styles.chalk}
        />
      ))}
      {arrows.map((arrow, i) => {
        const a = flip(arrow.from);
        const b = flip(arrow.to);
        return (
          <line
            // biome-ignore lint/suspicious/noArrayIndexKey: arrows have no identity beyond their order.
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            className={styles[arrow.kind]}
            style={arrow.colour ? { stroke: arrow.colour } : undefined}
            markerEnd="url(#td-head)"
          />
        );
      })}
      {frame.players.map((player) => {
        const look = players[player.playerId];
        const p = flip(player);
        const kit = kits[player.side];
        const dimmed = focus !== undefined && !focus.includes(player.playerId);
        return (
          <g key={player.playerId} transform={`translate(${p.x} ${p.y})`} opacity={dimmed ? 0.35 : 1}>
            <circle r={1.9} style={{ fill: kit.fill }} className={styles.player} />
            {look && (
              <text className={styles.number} style={{ fill: kit.ink }} dy={0.75}>
                {look.number}
              </text>
            )}
          </g>
        );
      })}
      <circle cx={ball.x} cy={ball.y} r={0.8} className={styles.ball} />
      {children}
    </svg>
  );
}
