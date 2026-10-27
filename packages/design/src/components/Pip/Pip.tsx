import cheer from "../../../illustration/pip-cheer.webp";
import neutral from "../../../illustration/pip-neutral.webp";
import phone from "../../../illustration/pip-phone.webp";
import remote from "../../../illustration/pip-remote.webp";
import sleep from "../../../illustration/pip-sleep.webp";
import think from "../../../illustration/pip-think.webp";
import wave from "../../../illustration/pip-wave.webp";
import whistle from "../../../illustration/pip-whistle.webp";

/** One drawn pose per moment (the generated sheet is in illustration/source). */
export type PipPose = "neutral" | "wave" | "whistle" | "remote" | "cheer" | "think" | "phone" | "sleep";

const art: Record<PipPose, string> = { neutral, wave, whistle, remote, cheer, think, phone, sleep };

interface PipProps {
  pose?: PipPose;
  /** Height in pixels; the width follows the drawing. */
  size: number;
  /** Empty by default: Pip is decoration next to words that already say what is going on. */
  alt?: string;
  className?: string;
}

/**
 * Pip, the robin who referees the room: the fair one who holds the remote. One Pip per screen, on our own
 * pages, setup, empty states and kid mode; never on the TV during play.
 */
export function Pip({ pose = "neutral", size, alt = "", className }: PipProps) {
  return <img src={art[pose]} alt={alt} height={size} className={className} style={{ width: "auto" }} />;
}
