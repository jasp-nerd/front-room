import { Button, type CastId, castColour, Helper, LensStrip, PhoneFrame } from "@frontroom/design";
import { type FormEvent, useEffect, useState } from "react";
import { type Depth, type Fan, fanById, privateDelivery, winnerId } from "../../fixtures/room";
import { latest, liveRoom, serverUrl, useRoomFeed } from "../../live/feed";
import { FitStage } from "../../ui/FitStage";
import { ShowcaseBar } from "../../ui/ShowcaseBar";
import { copy } from "./copy";
import { JoinPhone } from "./JoinPhone";
import styles from "./PhoneSurface.module.css";
import { boardSize, PhonesBoard } from "./PhonesBoard";
import { AnalystView } from "./views/AnalystView";
import { AudioView, type SpokenStory } from "./views/AudioView";
import { CasualView } from "./views/CasualView";
import { KidView } from "./views/KidView";
import { FocusBar, PlayerCardView } from "./views/PlayerFocus";
import views from "./views/views.module.css";
import { WhySheet } from "./WhySheet";

const SYNC_SECONDS = 38;
/** Kick-off 20:00, a 48-minute first half and a 15-minute break: the goal at 61:41 lands at 21:19 on a phone. */
const LOCAL_TIME = "21:19";

/**
 * Each lens shows its fan's story. `ownPick` is what the room sent this fan privately (nothing when their
 * pick is the one on the TV), so a lens never claims a delivery the room didn't make. `spoken` is the story
 * as audio, when the room server made it for a fan who listens.
 */
type LensProps = { fan: CastId; ownPick?: string; spoken?: SpokenStory };

const lenses: Record<Depth, (props: LensProps) => JSX.Element> = {
  analyst: AnalystView,
  casual: CasualView,
  kid: KidView,
  audio: AudioView,
};

/** The casual lens keeps a box for telling the helper, in thumb reach; the others have their own controls. */
const typesToHelper: Depth[] = ["casual"];

interface FanPhoneProps {
  fan: Fan;
  whyOpen?: boolean;
  token?: string;
  /**
   * Show the quiet waiting screen instead of the goal. By default a phone following a live room waits for
   * its first cue, so nothing appears before the TV shows it; a page that stages the room itself (the demo)
   * says when the TV has moved on.
   */
  waiting?: boolean;
}

export function FanPhone({ fan, whyOpen = false, token, waiting }: FanPhoneProps) {
  const [showWhy, setShowWhy] = useState(whyOpen);
  const words = copy[fan.lang];
  const Lens = lenses[fan.depth];
  const id = fan.id as CastId;
  const cue = latest(useRoomFeed("phone", fan.id, token ?? tokenFromUrl()), "cue")?.cue;
  const tvOverlay = cue ? String(cue.fields.tvOverlay) : winnerId();
  const yourPick = cue ? (cue.fields.onTv ? undefined : String(cue.fields.overlay)) : privateDelivery(fan.id);
  if (waiting ?? (liveRoom() !== null && !cue)) return <WaitingPhone fan={fan} />;
  return (
    <PhoneFrame time={LOCAL_TIME} lang={fan.lang} large={fan.depth === "audio"} accent={castColour[id]}>
      <LensStrip
        label={words.onTv}
        onTv={words.candidates[tvOverlay] ?? ""}
        behind={SYNC_SECONDS}
        sync={words.synced(SYNC_SECONDS)}
        why={words.why}
        onWhy={() => setShowWhy(true)}
      />
      <FocusBar fan={fan} />
      {yourPick?.startsWith("player-") ? (
        <PlayerCardView fan={fan} card={yourPick} />
      ) : (
        <Lens
          fan={id}
          {...(yourPick ? { ownPick: yourPick } : {})}
          {...(cue?.fields.audio
            ? {
                spoken: { src: String(cue.fields.audio), text: `${cue.fields.headline}. ${cue.fields.line}` },
              }
            : {})}
        />
      )}
      {typesToHelper.includes(fan.depth) && <TellHelper fan={fan} token={token ?? tokenFromUrl()} />}
      {showWhy && yourPick && (
        <WhySheet
          fanId={fan.id}
          winnerTitle={words.candidates[tvOverlay] ?? ""}
          yourPick={words.candidates[yourPick] ?? yourPick}
          onClose={() => setShowWhy(false)}
        />
      )}
    </PhoneFrame>
  );
}

/**
 * "More like this": the fan tells their own helper what they'd like more of. In a live room it goes to the
 * helper on the server (Content Safety screens it first); the room learns nothing until the helper's next asks.
 */
function TellHelper({ fan, token }: { fan: Fan; token: string | undefined }) {
  const words = copy[fan.lang];
  const [text, setText] = useState("");
  const [reply, setReply] = useState<string | null>(null);

  async function send(event: FormEvent) {
    event.preventDefault();
    const room = liveRoom();
    if (!text.trim()) return;
    if (!room || !token) {
      setReply(words.told);
      setText("");
      return;
    }
    const response = await fetch(serverUrl(`/rooms/${room}/fans/${fan.id}/more`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, told: text }),
    }).catch(() => null);
    const detail = response && !response.ok ? ((await response.json()) as { detail?: unknown }).detail : null;
    setReply(response?.ok ? words.told : typeof detail === "string" ? detail : words.told);
    if (response?.ok) setText("");
  }

  return (
    <form className={views.actions} onSubmit={send}>
      {reply && <p className={views.reply}>{reply}</p>}
      <input
        className={views.input}
        aria-label={words.tellAgent}
        placeholder={words.tellPlaceholder}
        value={text}
        maxLength={200}
        onChange={(event) => setText(event.target.value)}
      />
      <Button type="submit">{words.send}</Button>
    </form>
  );
}

/** A phone opened from its own link carries its token in the address: `/phone?fan=rob&live=1&token=…`. */
const tokenFromUrl = () => new URLSearchParams(window.location.search).get("token") ?? undefined;

/** Before the room's first moment: the phone is joined and quiet, and says so. */
function WaitingPhone({ fan }: { fan: Fan }) {
  const words = copy[fan.lang];
  const id = fan.id as CastId;
  return (
    <PhoneFrame time={LOCAL_TIME} lang={fan.lang} large={fan.depth === "audio"} accent={castColour[id]}>
      <div className={styles.waiting}>
        <div className={styles.waitingField}>
          <Helper id={id} size={170} />
        </div>
        <p className={styles.waitingTitle}>{words.waitingTitle}</p>
        <p className={styles.waitingLine}>{words.waitingLine}</p>
      </div>
    </PhoneFrame>
  );
}

/** `/phones`: the board fills the window, four across, or two by two on a phone held upright. */
function PhonesPage() {
  const upright = usePortrait();
  const columns = upright ? 2 : 4;
  return (
    <FitStage
      {...boardSize[columns]}
      header={
        <ShowcaseBar
          line="One goal, four phones: what each person on the sofa got from their own helper."
          action={{ href: "/demo?live=1", label: "Watch it live" }}
        />
      }
    >
      <PhonesBoard columns={columns} />
    </FitStage>
  );
}

function usePortrait(): boolean {
  const query = "(max-aspect-ratio: 1/1)";
  const [portrait, setPortrait] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const list = window.matchMedia(query);
    const change = () => setPortrait(list.matches);
    list.addEventListener("change", change);
    return () => list.removeEventListener("change", change);
  }, []);
  return portrait;
}

/**
 * `/phones` shows the whole room's phones side by side, `/phone?fan=rob&sheet=why` shows one,
 * and `/join?room=4821` is where the QR code on the TV leads.
 */
export function PhoneSurface() {
  const params = new URLSearchParams(window.location.search);
  if (window.location.pathname.startsWith("/join")) {
    return (
      <main className={styles.single}>
        <JoinPhone room={params.get("room") ?? "4821"} step={Number(params.get("step") ?? 1)} />
      </main>
    );
  }
  if (window.location.pathname.startsWith("/phones")) return <PhonesPage />;
  const fan = fanById(params.get("fan") ?? "rob");
  return (
    <main className={styles.single}>
      <FanPhone fan={fan} whyOpen={params.get("sheet") === "why"} />
    </main>
  );
}
