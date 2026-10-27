import type { PitchPoint, TrackingFrame } from "@frontroom/protocol";
import { useEffect, useRef } from "react";
import type { CameraRig, Vec3 } from "./camera";
import { type MatchPalette, type PlayerLook, renderMatch, type Telestration } from "./render";

/** A bright afternoon match: fresh grass, white lines, a pale stand under a clear sky. */
export const DAY_MATCH: MatchPalette = {
  sky: "#bfe2ff",
  stand: ["#cfdae6", "#d9e3ee"],
  crowd: ["#c8102e", "#6cace4", "#ffffff", "#14202f", "#ffc43d", "#8b95a5", "#c8102e", "#6cace4"],
  board: "#ffffff",
  boardLine: "#ffc43d",
  apron: "#2f9a54",
  grass: ["#3aa85e", "#44b469"],
  chalk: "rgba(255, 255, 255, 0.96)",
  signal: "#d63d15",
  kits: {
    home: { fill: "#c8102e", number: "#ffffff", edge: "#ffffff" },
    away: { fill: "#6cace4", number: "#14202f", edge: "#14202f" },
  },
  keeperKits: { home: "#14202f", away: "#ffc43d" },
  numberFont: '"Barlow Condensed", "Arial Narrow", sans-serif',
  labelFont: '"Figtree", system-ui, sans-serif',
  labelPlate: "#ffffff",
  labelInk: "#14202f",
  labelSpeed: "#ffc43d",
};

/** Where the gantry camera sits relative to the point it looks at. */
export interface CameraPlacement {
  /** Metres from the near touchline: negative is behind it. */
  back: number;
  height: number;
  fovDeg: number;
}

/** The main camera, following play from the halfway gantry. */
export const MAIN_CAMERA: CameraPlacement = { back: -36, height: 34, fovDeg: 31 };

interface MatchCanvasProps {
  frame: TrackingFrame;
  players: Record<string, PlayerLook>;
  target: Vec3;
  camera?: CameraPlacement;
  telestration?: Telestration;
  labels?: Record<string, string>;
  trail?: PitchPoint[];
  width: number;
  height: number;
  className?: string;
}

/** The match as a broadcast camera on a gantry above the near touchline would show it. */
export function MatchCanvas({
  frame,
  players,
  target,
  camera = MAIN_CAMERA,
  telestration,
  labels,
  trail,
  width,
  height,
  className,
}: MatchCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Size the drawing buffer once per size, not on every frame: during playback only the drawing changes.
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  }, [width, height]);

  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    const rig: CameraRig = {
      position: { x: target.x, y: camera.back, z: camera.height },
      target,
      fovDeg: camera.fovDeg,
      width,
      height,
    };
    const draw = () =>
      renderMatch(ctx, {
        frame,
        rig,
        palette: DAY_MATCH,
        players,
        ...(telestration ? { telestration } : {}),
        ...(labels ? { labels } : {}),
        ...(trail ? { trail } : {}),
      });
    draw();
    // Name tabs and shirt numbers are canvas text, so draw again once the brand fonts have loaded.
    let cancelled = false;
    document.fonts.ready.then(() => {
      if (!cancelled) draw();
    });
    return () => {
      cancelled = true;
    };
  }, [frame, players, target, camera, telestration, labels, trail, width, height]);

  return <canvas ref={canvasRef} className={className} style={{ width, height, display: "block" }} />;
}
