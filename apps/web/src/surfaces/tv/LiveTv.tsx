import { useEffect, useState } from "react";
import { clip } from "../../fixtures/goal";
import { latest, useRoomFeed } from "../../live/feed";
import { clipLengthMs } from "../../match/clip";
import { type Overlay, TvSurface } from "./TvSurface";

/**
 * The TV following a live room: the plain match until the room puts something on, then the replay with that
 * overlay, held for the cue's dwell time or until the replay ends, whichever is later, then back to the match.
 */
export function LiveTv() {
  const cue = latest(useRoomFeed("tv"), "cue")?.cue;
  const [onAir, setOnAir] = useState<Overlay | null>(null);

  useEffect(() => {
    if (!cue) return;
    const { headline, line, asked, inRoom, neutral } = cue.fields;
    setOnAir({
      headline: String(headline),
      line: String(line),
      asked: Number(asked),
      inRoom: Number(inRoom),
      neutral: Boolean(neutral),
    });
    const back = window.setTimeout(() => setOnAir(null), Math.max(cue.dwellMs, clipLengthMs(clip) + 2_000));
    return () => window.clearTimeout(back);
  }, [cue]);

  return onAir ? <TvSurface state="origin" overlay={onAir} /> : <TvSurface state="base" />;
}
