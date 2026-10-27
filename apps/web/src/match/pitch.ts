import type { Vec3 } from "./camera";

export const PITCH_LENGTH = 105;
export const PITCH_WIDTH = 68;

type Polyline = Vec3[];

const ground = (x: number, y: number): Vec3 => ({ x, y, z: 0 });

export function arc(cx: number, cy: number, r: number, fromDeg: number, toDeg: number, steps = 32): Polyline {
  return Array.from({ length: steps + 1 }, (_, i) => {
    const a = ((fromDeg + ((toDeg - fromDeg) * i) / steps) * Math.PI) / 180;
    return ground(cx + r * Math.cos(a), cy + r * Math.sin(a));
  });
}

function box(x0: number, y0: number, x1: number, y1: number): Polyline {
  return [ground(x0, y0), ground(x1, y0), ground(x1, y1), ground(x0, y1), ground(x0, y0)];
}

/** Every chalk line on a 105 × 68 pitch, as polylines on the ground plane. */
export function pitchMarkings(): Polyline[] {
  const L = PITCH_LENGTH;
  const W = PITCH_WIDTH;
  const mid = W / 2;
  const penaltyY = 40.32 / 2;
  const sixY = 18.32 / 2;
  // The penalty arc is the part of a 9.15 m circle around the spot that falls outside the box.
  const arcAngle = (Math.acos((16.5 - 11) / 9.15) * 180) / Math.PI;
  return [
    box(0, 0, L, W),
    [ground(L / 2, 0), ground(L / 2, W)],
    arc(L / 2, mid, 9.15, 0, 360, 64),
    box(0, mid - penaltyY, 16.5, mid + penaltyY),
    box(L - 16.5, mid - penaltyY, L, mid + penaltyY),
    box(0, mid - sixY, 5.5, mid + sixY),
    box(L - 5.5, mid - sixY, L, mid + sixY),
    arc(11, mid, 9.15, -arcAngle, arcAngle),
    arc(L - 11, mid, 9.15, 180 - arcAngle, 180 + arcAngle),
    arc(0, 0, 1, 0, 90, 8),
    arc(L, 0, 1, 90, 180, 8),
    arc(0, W, 1, 270, 360, 8),
    arc(L, W, 1, 180, 270, 8),
  ];
}

export const PITCH_SPOTS: Vec3[] = [
  ground(PITCH_LENGTH / 2, 34),
  ground(11, 34),
  ground(PITCH_LENGTH - 11, 34),
];

/** Mowing bands across the pitch, alternating shade. */
export function grassBands(count = 15): Polyline[] {
  const width = PITCH_LENGTH / count;
  return Array.from({ length: count }, (_, i) => box(i * width, 0, (i + 1) * width, PITCH_WIDTH).slice(0, 4));
}

/** The goal frame: two posts and a crossbar, 7.32 m wide and 2.44 m tall. */
export function goalFrame(atX: number): Polyline {
  const y0 = 34 - 3.66;
  const y1 = 34 + 3.66;
  return [
    { x: atX, y: y0, z: 0 },
    { x: atX, y: y0, z: 2.44 },
    { x: atX, y: y1, z: 2.44 },
    { x: atX, y: y1, z: 0 },
  ];
}
