import ana from "../../../illustration/fan-ana.webp";
import leo from "../../../illustration/fan-leo.webp";
import rob from "../../../illustration/fan-rob.webp";
import sam from "../../../illustration/fan-sam.webp";
import pink from "../../../illustration/helper-pink.webp";
import pitch from "../../../illustration/helper-pitch.webp";
import sky from "../../../illustration/helper-sky.webp";
import sun from "../../../illustration/helper-sun.webp";

/** The family on the demo sofa. Each has a colour, and their helper robin wears a scarf in it. */
export type CastId = "rob" | "ana" | "leo" | "sam";
export type CastColour = "sky" | "sun" | "pitch" | "pink";

export const castColour: Record<CastId, CastColour> = { rob: "sky", ana: "sun", leo: "pitch", sam: "pink" };

const faces: Record<CastId, string> = { rob, ana, leo, sam };
const helpers: Record<CastColour, string> = { sky, sun, pitch, pink };

interface CastProps {
  id: CastId;
  /** Height in pixels; the width follows the drawing. */
  size: number;
  alt?: string;
  className?: string;
}

/** A fan's drawn portrait, head and shoulders. */
export function FanFace({ id, size, alt = "", className }: CastProps) {
  return <img src={faces[id]} alt={alt} height={size} className={className} style={{ width: "auto" }} />;
}

/** A fan's helper: a little robin in that fan's scarf, asking for the TV on their behalf. */
export function Helper({ id, size, alt = "", className }: CastProps) {
  return (
    <img
      src={helpers[castColour[id]]}
      alt={alt}
      height={size}
      className={className}
      style={{ width: "auto" }}
    />
  );
}
