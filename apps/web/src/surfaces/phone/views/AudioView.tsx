import type { CastId } from "@frontroom/design";
import { useRef, useState } from "react";
import { regain } from "../../../fixtures/goal";
import { serverUrl } from "../../../live/feed";
import audio from "./AudioView.module.css";
import styles from "./views.module.css";

/** The story as the room server spoke it (Azure AI Speech): a private link to the mp3, and its words. */
export interface SpokenStory {
  src: string;
  text: string;
}

/** Until the room has spoken a story, the lens shows the demo's description at a resting point. */
const SAMPLE = { elapsed: 12, length: 31 };

const time = (s: number) => {
  const whole = Math.max(0, Math.round(s));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
};

/** Icons are 2px strokes on a 24px grid with square caps. */
function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" className={audio.icon} aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

/**
 * The audio-first lens: useful with the screen off. Large type, big controls, the words being spoken. When
 * the room server has spoken the story, the controls play it; otherwise they show where the description is.
 */
export function AudioView({ spoken }: { fan: CastId; spoken?: SpokenStory }) {
  const player = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(spoken ? 0 : SAMPLE.elapsed);
  const [length, setLength] = useState(spoken ? 0 : SAMPLE.length);

  const toggle = () => {
    const clip = player.current;
    if (!clip) return;
    if (clip.paused) {
      // A blocked play (no tap yet, or the clip failed) leaves the words on screen, which is the fallback.
      clip.play().catch(() => setPlaying(false));
    } else {
      clip.pause();
    }
  };
  const back = () => {
    if (player.current) player.current.currentTime = Math.max(0, player.current.currentTime - 10);
  };

  return (
    <div className={styles.content}>
      <section className={styles.block}>
        <p className={audio.playing}>In your earbuds</p>
        <h2 className={styles.headline}>Where it started, described</h2>
        <p className={audio.transcript}>
          {spoken
            ? spoken.text
            : `Kestrel press high. ${regain.player} steps in front of Lund on halfway and takes the ball.`}
        </p>
      </section>
      <section className={styles.block}>
        {spoken && (
          // biome-ignore lint/a11y/useMediaCaption: the transcript above is the caption, word for word.
          <audio
            ref={player}
            src={serverUrl(spoken.src)}
            preload="auto"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onLoadedMetadata={(e) => setLength(e.currentTarget.duration)}
            onTimeUpdate={(e) => setElapsed(e.currentTarget.currentTime)}
          />
        )}
        <div
          className={audio.progress}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={Math.round(length)}
          aria-valuenow={Math.round(elapsed)}
          aria-label="Description progress"
        >
          <span style={{ width: `${length ? (elapsed / length) * 100 : 0}%` }} />
        </div>
        <p className={audio.times}>
          <span>{time(elapsed)}</span>
          <span>{time(length)}</span>
        </p>
        <div className={audio.controls}>
          <button type="button" className={audio.control} aria-label="Back 10 seconds" onClick={back}>
            <Icon d="M10 7 5 12l5 5M5 12h14" />
          </button>
          <button
            type="button"
            className={audio.pause}
            aria-label={playing || !spoken ? "Pause" : "Play"}
            onClick={toggle}
          >
            {playing || !spoken ? <Icon d="M9 6v12M15 6v12" /> : <Icon d="M8 5v14l11-7z" />}
          </button>
          <button type="button" className={audio.control} aria-label="Next">
            <Icon d="M14 7l5 5-5 5M19 12H5" />
          </button>
        </div>
      </section>
      <p className={styles.lede}>Next: Kestrel's pressing map, described.</p>
      <p className={styles.note}>Your phone buzzes once for a goal and twice for a card.</p>
    </div>
  );
}
