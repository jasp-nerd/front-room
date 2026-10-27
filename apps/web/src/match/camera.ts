/**
 * A broadcast camera: a pinhole camera on a gantry above the near touchline that pans to follow play.
 * World coordinates are pitch metres: x along the touchline (0–105), y across the pitch (0–68), z up.
 */

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface ScreenPoint {
  x: number;
  y: number;
  /** Distance from the camera along its view axis; used for depth sorting and scaling. */
  depth: number;
}

export interface CameraRig {
  /** Gantry position: behind the near touchline (negative y) and raised. */
  position: Vec3;
  /** Point on the pitch the camera looks at. */
  target: Vec3;
  /** Vertical field of view in degrees. A broadcast main camera sits around 18–28°. */
  fovDeg: number;
  width: number;
  height: number;
}

const sub = (a: Vec3, b: Vec3): Vec3 => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
const dot = (a: Vec3, b: Vec3) => a.x * b.x + a.y * b.y + a.z * b.z;
const cross = (a: Vec3, b: Vec3): Vec3 => ({
  x: a.y * b.z - a.z * b.y,
  y: a.z * b.x - a.x * b.z,
  z: a.x * b.y - a.y * b.x,
});
const normalize = (v: Vec3): Vec3 => {
  const length = Math.hypot(v.x, v.y, v.z);
  return { x: v.x / length, y: v.y / length, z: v.z / length };
};

export interface Projector {
  project(point: Vec3): ScreenPoint | null;
  /** Pixels per metre at a given depth, for sizing players and rings consistently with perspective. */
  scaleAt(depth: number): number;
}

export function createProjector(rig: CameraRig): Projector {
  const forward = normalize(sub(rig.target, rig.position));
  const right = normalize(cross(forward, { x: 0, y: 0, z: 1 }));
  const up = cross(right, forward);
  const focal = rig.height / 2 / Math.tan((rig.fovDeg * Math.PI) / 360);

  return {
    project(point) {
      const relative = sub(point, rig.position);
      const depth = dot(relative, forward);
      if (depth <= 0.1) return null;
      return {
        x: rig.width / 2 + (focal * dot(relative, right)) / depth,
        y: rig.height / 2 - (focal * dot(relative, up)) / depth,
        depth,
      };
    },
    scaleAt(depth) {
      return focal / depth;
    },
  };
}

/** Where the gantry camera should look: follows the ball along the pitch, eased so it never jerks. */
export function followTarget(previous: Vec3, ball: Vec3, smoothing: number): Vec3 {
  const desired = { x: clamp(ball.x, 22, 83), y: clamp(ball.y * 0.55 + 12, 18, 36), z: 0 };
  return {
    x: previous.x + (desired.x - previous.x) * smoothing,
    y: previous.y + (desired.y - previous.y) * smoothing,
    z: 0,
  };
}

export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
