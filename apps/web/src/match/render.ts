import type { PitchPoint, TrackingFrame } from "@frontroom/protocol";
import { type CameraRig, createProjector, type Projector, type Vec3 } from "./camera";
import { arc, goalFrame, grassBands, PITCH_LENGTH, PITCH_SPOTS, pitchMarkings } from "./pitch";

export interface MatchPalette {
  /** Behind the stand, wherever the camera sees past it. */
  sky: string;
  stand: [string, string];
  /** Shirts in the crowd, picked per seat so the stand looks full but never moves. */
  crowd: string[];
  /** The advertising board in front of the stand, and the one lit line along its top. */
  board: string;
  boardLine: string;
  apron: string;
  grass: [string, string];
  chalk: string;
  signal: string;
  kits: Record<"home" | "away", { fill: string; number: string; edge: string }>;
  keeperKits: Record<"home" | "away", string>;
  numberFont: string;
  labelFont: string;
  labelPlate: string;
  labelInk: string;
  /** Behind the speed a sprinting player's tab shows. */
  labelSpeed: string;
}

/** Drawn on the grass: where a goal started, and the passes that followed. */
export interface Telestration {
  origin?: PitchPoint;
  path?: PitchPoint[];
}

export interface PlayerLook {
  number: number;
  isKeeper: boolean;
}

export interface RenderInput {
  frame: TrackingFrame;
  rig: CameraRig;
  palette: MatchPalette;
  players: Record<string, PlayerLook>;
  telestration?: Telestration;
  /** Name tabs above the players a story is about, by player id. */
  labels?: Record<string, string>;
  /** Where the ball has just travelled, oldest point first; drawn as a fading line on the grass. */
  trail?: PitchPoint[];
}

export function renderMatch(ctx: CanvasRenderingContext2D, input: RenderInput): Projector {
  const { rig, palette } = input;
  const projector = createProjector(rig);

  ctx.fillStyle = palette.sky;
  ctx.fillRect(0, 0, rig.width, rig.height);

  drawStand(ctx, projector, palette);
  drawGround(ctx, projector, palette);
  drawLines(ctx, projector, palette);
  if (input.trail) drawTrail(ctx, projector, input.trail, palette);
  if (input.telestration) drawTelestration(ctx, projector, input.telestration, palette);
  drawPeople(ctx, projector, input);
  if (input.labels) drawLabels(ctx, projector, input);
  return projector;
}

function fillPolygon(ctx: CanvasRenderingContext2D, projector: Projector, points: Vec3[], color: string) {
  const projected = points.map((p) => projector.project(p));
  if (projected.some((p) => p === null)) return;
  ctx.beginPath();
  projected.forEach((p, i) => {
    if (!p) return;
    if (i === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

function strokePolyline(ctx: CanvasRenderingContext2D, projector: Projector, points: Vec3[]) {
  ctx.beginPath();
  let drawing = false;
  for (const point of points) {
    const p = projector.project(point);
    if (!p) {
      drawing = false;
      continue;
    }
    if (drawing) ctx.lineTo(p.x, p.y);
    else ctx.moveTo(p.x, p.y);
    drawing = true;
  }
  ctx.stroke();
}

/**
 * A stand behind the far touchline in two alternating tiers, kept pale and still so the eye stays on the
 * pitch, with a white advertising board in front and one sun-yellow line along its top.
 */
function drawStand(ctx: CanvasRenderingContext2D, projector: Projector, palette: MatchPalette) {
  const tierHeight = 2.2;
  for (let tier = 0; tier < 8; tier += 1) {
    const y = 74 + tier * 2.4;
    const z0 = 1.2 + tier * tierHeight;
    fillPolygon(
      ctx,
      projector,
      [
        { x: -60, y, z: z0 },
        { x: PITCH_LENGTH + 60, y, z: z0 },
        { x: PITCH_LENGTH + 60, y: y + 2.4, z: z0 + tierHeight },
        { x: -60, y: y + 2.4, z: z0 + tierHeight },
      ],
      palette.stand[tier % 2] ?? palette.sky,
    );
    drawCrowd(ctx, projector, palette, tier, y + 1.2, z0 + tierHeight * 0.5);
  }
  const board = (z0: number, z1: number): Vec3[] => [
    { x: -30, y: 71.5, z: z0 },
    { x: PITCH_LENGTH + 30, y: 71.5, z: z0 },
    { x: PITCH_LENGTH + 30, y: 71.5, z: z1 },
    { x: -30, y: 71.5, z: z1 },
  ];
  fillPolygon(ctx, projector, board(0, 1.1), palette.board);
  fillPolygon(ctx, projector, board(1.02, 1.1), palette.boardLine);
}

/** Two rows of supporters along a tier: a dot per seat, its colour fixed by the seat so nothing flickers. */
function drawCrowd(
  ctx: CanvasRenderingContext2D,
  projector: Projector,
  palette: MatchPalette,
  tier: number,
  y: number,
  z: number,
) {
  for (let row = 0; row < 2; row += 1) {
    for (let seat = 0; seat < 320; seat += 1) {
      const x = -60 + seat * 0.7 + row * 0.35;
      const p = projector.project({ x, y: y + row * 0.9 - 0.45, z: z + row * 0.8 - 0.4 });
      if (!p) continue;
      // An integer hash of the seat picks the shirt; about one seat in eight stays empty.
      const hash = Math.imul(seat + 1, 2654435761) ^ Math.imul(tier * 2 + row + 1, 40503);
      const pick = (hash >>> 8) % 64;
      if (pick < 8) continue;
      const r = Math.max(1.5, projector.scaleAt(p.depth) * 0.28);
      ctx.fillStyle = palette.crowd[pick % palette.crowd.length] ?? palette.sky;
      ctx.beginPath();
      ctx.ellipse(p.x, p.y, r, r * 1.15, 0, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function drawGround(ctx: CanvasRenderingContext2D, projector: Projector, palette: MatchPalette) {
  fillPolygon(
    ctx,
    projector,
    [
      { x: -60, y: -40, z: 0 },
      { x: PITCH_LENGTH + 60, y: -40, z: 0 },
      { x: PITCH_LENGTH + 60, y: 71.5, z: 0 },
      { x: -60, y: 71.5, z: 0 },
    ],
    palette.apron,
  );
  grassBands().forEach((band, i) => {
    fillPolygon(ctx, projector, band, palette.grass[i % 2] ?? palette.apron);
  });
}

function drawLines(ctx: CanvasRenderingContext2D, projector: Projector, palette: MatchPalette) {
  ctx.strokeStyle = palette.chalk;
  ctx.lineWidth = Math.max(1.5, projector.scaleAt(60) * 0.12);
  ctx.lineJoin = "round";
  for (const line of pitchMarkings()) strokePolyline(ctx, projector, line);
  ctx.fillStyle = palette.chalk;
  for (const spot of PITCH_SPOTS) {
    const p = projector.project(spot);
    if (!p) continue;
    const r = projector.scaleAt(p.depth) * 0.22;
    ctx.beginPath();
    ctx.ellipse(p.x, p.y, r, r * 0.45, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  drawGoal(ctx, projector, 0, -1);
  drawGoal(ctx, projector, PITCH_LENGTH, 1);
}

/** Posts and crossbar, plus a faint net box running back from the line so the goal reads as a goal. */
function drawGoal(ctx: CanvasRenderingContext2D, projector: Projector, x: number, out: 1 | -1) {
  const back = x + out * 2;
  const frame = goalFrame(x);
  const net = goalFrame(back).map((p) => ({ ...p, z: p.z * 0.8 }));
  ctx.lineWidth = Math.max(1, projector.scaleAt(60) * 0.05);
  ctx.globalAlpha = 0.45;
  strokePolyline(ctx, projector, net);
  for (const [i, post] of frame.entries()) {
    const corner = net[i];
    if (corner) strokePolyline(ctx, projector, [post, corner]);
  }
  ctx.globalAlpha = 1;
  ctx.lineWidth = Math.max(2, projector.scaleAt(60) * 0.16);
  strokePolyline(ctx, projector, frame);
}

function drawTrail(
  ctx: CanvasRenderingContext2D,
  projector: Projector,
  trail: PitchPoint[],
  palette: MatchPalette,
) {
  ctx.strokeStyle = palette.chalk;
  ctx.lineCap = "butt";
  ctx.lineWidth = Math.max(3, projector.scaleAt(50) * 0.2);
  // Split each leg into short pieces that fade in towards the ball.
  const pieces = 12;
  for (let leg = 0; leg < trail.length - 1; leg += 1) {
    const from = trail[leg];
    const to = trail[leg + 1];
    if (!from || !to) continue;
    for (let i = 0; i < pieces; i += 1) {
      const t0 = i / pieces;
      const t1 = (i + 1) / pieces;
      ctx.globalAlpha = 0.1 + 0.65 * t1;
      strokePolyline(ctx, projector, [
        { x: from.x + (to.x - from.x) * t0, y: from.y + (to.y - from.y) * t0, z: 0 },
        { x: from.x + (to.x - from.x) * t1, y: from.y + (to.y - from.y) * t1, z: 0 },
      ]);
    }
  }
  ctx.globalAlpha = 1;
}

function drawTelestration(
  ctx: CanvasRenderingContext2D,
  projector: Projector,
  telestration: Telestration,
  palette: MatchPalette,
) {
  ctx.strokeStyle = palette.signal;
  ctx.fillStyle = palette.signal;
  ctx.lineCap = "round";

  const path = telestration.path ?? [];
  if (path.length > 1) {
    ctx.lineWidth = Math.max(3, projector.scaleAt(50) * 0.32);
    ctx.setLineDash([ctx.lineWidth * 3, ctx.lineWidth * 2]);
    strokePolyline(
      ctx,
      projector,
      path.map((p) => ({ x: p.x, y: p.y, z: 0 })),
    );
    ctx.setLineDash([]);
    for (const node of path.slice(1, -1)) {
      ctx.lineWidth = Math.max(2, projector.scaleAt(50) * 0.2);
      strokePolyline(ctx, projector, arc(node.x, node.y, 0.9, 0, 360, 24));
    }
    drawArrowhead(ctx, projector, path);
  }

  if (telestration.origin) {
    ctx.lineWidth = Math.max(4, projector.scaleAt(50) * 0.4);
    strokePolyline(ctx, projector, arc(telestration.origin.x, telestration.origin.y, 2.6, 0, 360, 48));
  }
}

function drawArrowhead(ctx: CanvasRenderingContext2D, projector: Projector, path: PitchPoint[]) {
  const end = path.at(-1);
  const before = path.at(-2);
  if (!end || !before) return;
  const length = Math.hypot(end.x - before.x, end.y - before.y);
  const ux = (end.x - before.x) / length;
  const uy = (end.y - before.y) / length;
  const size = 2.2;
  const left = { x: end.x - ux * size - uy * size * 0.6, y: end.y - uy * size + ux * size * 0.6, z: 0 };
  const right = { x: end.x - ux * size + uy * size * 0.6, y: end.y - uy * size - ux * size * 0.6, z: 0 };
  const points = [left, { ...end, z: 0 }, right].map((p) => projector.project(p));
  if (points.some((p) => !p)) return;
  ctx.beginPath();
  points.forEach((p, i) => {
    if (!p) return;
    if (i === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.closePath();
  ctx.fill();
}

interface Drawable {
  depth: number;
  draw: () => void;
}

/** Players and the ball, far to near, so nearer markers overlap farther ones. */
function drawPeople(ctx: CanvasRenderingContext2D, projector: Projector, input: RenderInput) {
  const { frame, palette, players } = input;
  const drawables: Drawable[] = [];

  for (const player of frame.players) {
    const foot = projector.project({ x: player.x, y: player.y, z: 0 });
    const head = projector.project({ x: player.x, y: player.y, z: 2.0 });
    if (!foot || !head) continue;
    const look = players[player.playerId];
    const kit = palette.kits[player.side];
    const fill = look?.isKeeper ? palette.keeperKits[player.side] : kit.fill;
    drawables.push({
      depth: foot.depth,
      draw: () => {
        const scale = projector.scaleAt(foot.depth);
        const half = Math.max(5, scale * 0.52);
        ctx.fillStyle = "rgba(10, 40, 20, 0.28)";
        ctx.beginPath();
        ctx.ellipse(foot.x, foot.y, half * 1.5, half * 0.5, 0, 0, Math.PI * 2);
        ctx.fill();
        // A player is an upright capsule, as tall as a person, with the shirt number on the chest.
        const top = head.y;
        const bottom = foot.y - half * 0.2;
        ctx.beginPath();
        ctx.roundRect(foot.x - half, top, half * 2, bottom - top, half);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.lineWidth = Math.max(1, half * 0.16);
        ctx.strokeStyle = kit.edge;
        ctx.stroke();
        if (look && half >= 7) {
          ctx.fillStyle = kit.number;
          ctx.font = `700 ${Math.round(half * 1.35)}px ${palette.numberFont}`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(String(look.number), foot.x, top + half * 1.45);
        }
      },
    });
  }

  const ball = frame.ball;
  const ballPoint = projector.project({ x: ball.x, y: ball.y, z: ball.z + 0.11 });
  const ballShadow = projector.project({ x: ball.x, y: ball.y, z: 0 });
  if (ballPoint && ballShadow) {
    drawables.push({
      depth: ballShadow.depth - 0.01,
      draw: () => {
        const r = Math.max(3, projector.scaleAt(ballShadow.depth) * 0.22);
        ctx.fillStyle = "rgba(10, 40, 20, 0.3)";
        ctx.beginPath();
        ctx.ellipse(ballShadow.x, ballShadow.y, r, r * 0.4, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(ballPoint.x, ballPoint.y, r, 0, Math.PI * 2);
        ctx.fill();
      },
    });
  }

  for (const drawable of drawables.sort((a, b) => b.depth - a.depth)) drawable.draw();
}

/** High-speed running (19.8 km/h, the standard tracking band) shows on a tagged player's tab. */
const HIGH_SPEED_MS = 5.5;

/**
 * A name on a white tab above each labelled player's head, kept clear of the player below. When players
 * bunch up, a tab that would cover one already drawn is lifted above it. While a tagged player runs at high
 * speed, the tab grows a sun-yellow end with their speed from the tracking.
 */
function drawLabels(ctx: CanvasRenderingContext2D, projector: Projector, input: RenderInput) {
  const { frame, palette, labels = {} } = input;
  ctx.font = `700 24px ${palette.labelFont}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const placed: { x: number; y: number; width: number; height: number }[] = [];
  for (const player of frame.players) {
    const name = labels[player.playerId];
    const head = projector.project({ x: player.x, y: player.y, z: 2.0 });
    if (!name || !head) continue;
    const sprinting = player.speed >= HIGH_SPEED_MS;
    const speed = sprinting ? `${Math.round(player.speed * 3.6)} km/h` : "";
    const nameWidth = ctx.measureText(name).width + 24;
    const speedWidth = sprinting ? ctx.measureText(speed).width + 20 : 0;
    const width = nameWidth + speedWidth;
    const height = 38;
    const x = head.x - width / 2;
    let y = head.y - height - 10;
    const overlaps = (r: (typeof placed)[number]) =>
      x < r.x + r.width && r.x < x + width && y < r.y + r.height + 6 && r.y < y + height + 6;
    for (let tries = 0; tries < 4 && placed.some(overlaps); tries += 1) y -= height + 8;
    placed.push({ x, y, width, height });
    // The same flat lip as the TV's cards, so a tab reads as one of ours over the grass.
    ctx.fillStyle = "rgba(20, 32, 47, 0.25)";
    ctx.beginPath();
    ctx.roundRect(x, y + 4, width, height, height / 2);
    ctx.fill();
    ctx.fillStyle = palette.labelPlate;
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, height / 2);
    ctx.fill();
    if (sprinting) {
      ctx.save();
      ctx.beginPath();
      ctx.roundRect(x, y, width, height, height / 2);
      ctx.clip();
      ctx.fillStyle = palette.labelSpeed;
      ctx.fillRect(x + nameWidth, y, speedWidth, height);
      ctx.restore();
    }
    ctx.fillStyle = palette.labelInk;
    ctx.fillText(name, x + nameWidth / 2, y + height / 2 + 1);
    if (sprinting) ctx.fillText(speed, x + nameWidth + speedWidth / 2, y + height / 2 + 1);
  }
}
