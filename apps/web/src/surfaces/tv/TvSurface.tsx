import { type CaptionLine, Captions, LowerThird, ScoreBug } from "@frontroom/design";
import { useState } from "react";
import { clip, clipMs, firstPress, frameAtClock, goal, secondHalfClock } from "../../fixtures/goal";
import { askedForWinner, fans } from "../../fixtures/room";
import { ClipReplay } from "../../match/ClipReplay";
import { followAt, looks } from "../../match/clip";
import { MatchCanvas } from "../../match/MatchCanvas";
import styles from "./TvSurface.module.css";

export type TvState = "base" | "origin";

const captions: Record<TvState, CaptionLine[]> = {
  base: [
    { lang: "en", text: "Lund on the ball near halfway, Mensah closing in" },
    { lang: "es", text: "Lund con el balón en el centro, Mensah presiona" },
  ],
  origin: [
    { lang: "en", text: "Replay of the build-up to Okafor's goal" },
    { lang: "es", text: "Repetición de la jugada del gol de Okafor" },
  ],
};

/** What the room put on the TV: the lower third's words and how the room decided. */
export interface Overlay {
  headline: string;
  line: string;
  asked: number;
  inRoom: number;
  neutral: boolean;
}

/** The demo room's overlay: the writer agent's copy for the engine's goal, and how the demo room decided. */
const demoOverlay: Overlay = {
  headline: goal.copy.en_headline,
  line: goal.copy.en_line,
  asked: askedForWinner().length,
  inRoom: fans.length,
  neutral: true,
};

/**
 * The live picture before the goal: a moment before Mensah presses, with Lund on the ball. The camera
 * follows the ball as the main gantry camera does.
 */
const liveClock = firstPress.clockMs - 300;
const liveFrame = frameAtClock(liveClock);
const liveCamera = followAt(clip, clipMs(liveClock), false);
const players = looks(clip);

interface TvSurfaceProps {
  state: TvState;
  overlay?: Overlay;
  /** A household can hide the "how the room decided" line; the overlay itself stays. */
  showProvenance?: boolean;
  /** Replay the goal again and again, for a showcase rather than a living room. */
  loopReplay?: boolean;
  /** Keep the room's overlay up for the whole replay instead of bringing it in at the press. */
  overlayThroughout?: boolean;
  /** Hold the lower third back (the guided demo shows it once the room has decided). */
  lowerThird?: boolean;
  /** Start the replay this far into the clip and play it this many times faster. */
  replayFromMs?: number;
  replaySpeed?: number;
}

/** The replay of the goal plays from the engine's tracking; `?replay=0` shows its last frame as a still. */
const replayRequested = () => new URLSearchParams(window.location.search).get("replay") !== "0";

/** The shared screen in the room: the match, the one overlay the room agreed on, and captions. */
export function TvSurface({
  state,
  overlay = demoOverlay,
  showProvenance = true,
  loopReplay = false,
  overlayThroughout = false,
  lowerThird = true,
  replayFromMs = 0,
  replaySpeed = 1,
}: TvSurfaceProps) {
  const showOrigin = state === "origin";
  const replay = showOrigin && replayRequested();
  // During a replay the lower third comes in once play reaches the action the move started with.
  const [replayMs, setReplayMs] = useState(0);
  const firstAction = clipMs(firstPress.clockMs);
  const lowerThirdOn = lowerThird && showOrigin && (!replay || overlayThroughout || replayMs >= firstAction);
  return (
    <main className={styles.screen}>
      {showOrigin ? (
        <ClipReplay
          clip={clip}
          width={1920}
          height={1080}
          className={styles.match}
          onTime={setReplayMs}
          loop={loopReplay}
          fromMs={replayFromMs}
          speed={replaySpeed}
          {...(replay ? {} : { atMs: clipMs(goal.chain[goal.chain.length - 1]?.clockMs ?? 0) })}
        />
      ) : (
        <MatchCanvas
          frame={liveFrame}
          players={players}
          target={liveCamera}
          width={1920}
          height={1080}
          className={styles.match}
        />
      )}
      <div className={styles.topLeft}>
        <ScoreBug
          home={{
            short: "KES",
            colour: "var(--club-kestrel)",
            ink: "var(--on-club-kestrel)",
            goals: (showOrigin ? goal.scoreAfter : goal.scoreBefore).home,
          }}
          away={{
            short: "ASH",
            colour: "var(--club-ashvale)",
            ink: "var(--on-club-ashvale)",
            goals: (showOrigin ? goal.scoreAfter : goal.scoreBefore).away,
          }}
          clock={showOrigin ? goal.goalClock : secondHalfClock(liveClock)}
        />
      </div>
      {showOrigin && (
        <div className={styles.topRight}>
          <span className={styles.replay}>Replay</span>
          <span className={styles.replayTime}>{goal.regainClock}</span>
        </div>
      )}
      <div className={styles.bottom}>
        {lowerThirdOn && <LowerThird {...overlay} showProvenance={showProvenance} />}
        <Captions lines={captions[state]} />
      </div>
    </main>
  );
}
