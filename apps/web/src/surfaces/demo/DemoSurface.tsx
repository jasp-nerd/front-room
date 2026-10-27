import { type CastId, FanFace, Helper, Pip, type PipPose, Wordmark } from "@frontroom/design";
import type { Decision } from "@frontroom/protocol";
import { useEffect, useMemo, useState } from "react";
import { clip, clipMs, firstPress, goal } from "../../fixtures/goal";
import { candidates, type Fan, fans } from "../../fixtures/room";
import { latest, serverUrl } from "../../live/feed";
import { clipLengthMs } from "../../match/clip";
import { Scaled } from "../../ui/Scaled";
import { FanPhone } from "../phone/PhoneSurface";
import { type Overlay, TvSurface } from "../tv/TvSurface";
import styles from "./DemoSurface.module.css";
import { NextButton } from "./NextButton";
import {
  askLine,
  favourites,
  gotLine,
  holdFor,
  listNames,
  outnumbered,
  stampFor,
  stepLine,
  titleOf,
  unhappy,
  waitTipped,
  whyItWon,
} from "./story";
import { useDemoRoom } from "./useDemoRoom";

/** The story, one beat at a time: the sofa, the goal, the asks, Pip's pick, and the phones lighting up. */
type Stage = "sofa" | "goal" | "asks" | "pick" | "phones";
const STAGES: Stage[] = ["sofa", "goal", "asks", "pick", "phones"];

const look: Record<Stage, { pip: PipPose; field: string }> = {
  sofa: { pip: "wave", field: "sky" },
  goal: { pip: "cheer", field: "sun" },
  asks: { pip: "think", field: "sky" },
  pick: { pip: "whistle", field: "pitch" },
  phones: { pip: "phone", field: "pink" },
};

/** The replay starts just before Mensah's press and runs half as fast again, so the goal goes in after about
 * fourteen seconds: about when the live investigation finishes. */
const REPLAY_FROM_MS = clipMs(firstPress.clockMs) - 600;
const REPLAY_SPEED = 1.5;
const REPLAY_MS = clipLengthMs(clip);
const GOAL_IN_MS = (clipMs(goal.chain[goal.chain.length - 1]?.clockMs ?? 0) - REPLAY_FROM_MS) / REPLAY_SPEED;
/** In Pip's beat: the cards shuffle, then the winner and the stamps show. */
const REVEAL_AFTER_MS = 900;
/** In the phones' beat: one phone lights up after another. */
const FIRST_PHONE_MS = 700;
const BETWEEN_PHONES_MS = 1_200;

const AWAY = "ana";

interface ReplayRun {
  n: number;
  speed: number;
  slower: boolean;
}

/**
 * The live demo: four fans on a real room on the room server. The goal's replay starts the moment the visitor
 * presses play, while the agents work; then each helper asks for the TV, Pip picks, and the phones light up
 * one by one. Each beat stays up long enough to read it, and "Next" moves on early.
 */
export function DemoSurface() {
  const { room, tokens, join, playing, messages, play, again } = useDemoRoom();
  const [stage, setStage] = useState<Stage>("sofa");
  const [me, setMe] = useState<string | null>(null);
  const [away, setAway] = useState(false);
  const [replay, setReplay] = useState<ReplayRun | null>(null);
  const [goalSeen, setGoalSeen] = useState(false);
  const [flash, setFlash] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [lit, setLit] = useState(0);
  const [models, setModels] = useState<string | null>(null);

  const decision = latest(messages, "decision");
  const insight = latest(messages, "insight");
  const present = useMemo(() => fans.filter((f) => !(away && f.id === AWAY)), [away]);

  useEffect(() => {
    fetch(serverUrl("/health"))
      .then((r) => r.json())
      .then((health: { live: boolean; models?: string }) =>
        setModels(
          !health.live
            ? "Rule-based helpers (no model access here)"
            : health.models === "foundry"
              ? "Helpers on Microsoft Foundry"
              : "Helpers on Azure OpenAI",
        ),
      )
      .catch(() => setModels(null));
  }, []);

  /** The goal goes in: the replay starts at once, while the room server works. */
  function start(withoutAna = away) {
    setStage("goal");
    setRevealed(false);
    setLit(0);
    setGoalSeen(false);
    setReplay((r) => ({ n: (r?.n ?? 0) + 1, speed: REPLAY_SPEED, slower: false }));
    setFlash(true);
    if (playing || withoutAna !== away) again(withoutAna ? AWAY : undefined);
    else play();
  }

  useEffect(() => {
    if (!flash) return;
    const off = window.setTimeout(() => setFlash(false), 1_800);
    return () => window.clearTimeout(off);
  }, [flash]);

  // The goal has to go in on the replay before the story moves on; if the room hasn't decided by the end of
  // the replay, it plays again, slower.
  useEffect(() => {
    if (!replay) return;
    const timers: number[] = [];
    if (!replay.slower) timers.push(window.setTimeout(() => setGoalSeen(true), GOAL_IN_MS + 600));
    if (!decision) {
      const ends = (REPLAY_MS - REPLAY_FROM_MS) / replay.speed + 400;
      timers.push(window.setTimeout(() => setReplay({ n: replay.n + 1, speed: 1, slower: true }), ends));
    }
    return () => timers.forEach(window.clearTimeout);
  }, [replay, decision]);

  useEffect(() => {
    if (stage !== "pick") return;
    const show = window.setTimeout(() => setRevealed(true), REVEAL_AFTER_MS);
    return () => window.clearTimeout(show);
  }, [stage]);

  useEffect(() => {
    if (stage !== "phones") return;
    const timers = present.map((_, i) =>
      window.setTimeout(() => setLit(i + 1), FIRST_PHONE_MS + i * BETWEEN_PHONES_MS),
    );
    return () => timers.forEach(window.clearTimeout);
  }, [stage, present]);

  const advance = () => setStage((s) => STAGES[Math.min(STAGES.indexOf(s) + 1, STAGES.length - 1)] ?? s);

  const wire = decision?.decision;
  const asks = useMemo(() => (decision ? favourites(decision.bids) : new Map<string, string>()), [decision]);
  const winnerId = wire?.candidates.find((c) => c.won)?.candidateId;
  const allLit = stage === "phones" && lit >= present.length;

  const overlay: Overlay | undefined =
    wire && winnerId ? tvOverlay(wire, winnerId, insight?.copy, present) : undefined;
  const latestStep = [...messages].reverse().find((m) => m.type === "step");

  const beat = copyFor(stage, wire, present, winnerId);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <a href="/" aria-label="Front Room, home">
          <Wordmark variant="lockup" height={22} />
        </a>
        {models !== null && <span className={styles.mode}>{models}</span>}
        <a className={styles.how} href="/how">
          How it works
        </a>
      </header>

      <section className={styles.tv} aria-label="The TV">
        <Scaled width={1920} height={1080}>
          {replay ? (
            <TvSurface
              key={replay.n}
              state="origin"
              replayFromMs={REPLAY_FROM_MS}
              replaySpeed={replay.speed}
              lowerThird={Boolean(overlay) && (stage === "phones" || (stage === "pick" && revealed))}
              overlayThroughout
              {...(overlay ? { overlay } : {})}
            />
          ) : (
            <TvSurface state="base" />
          )}
        </Scaled>
        {flash && (
          <p className={styles.goalFlash} aria-hidden="true">
            Goal!
          </p>
        )}
        {replay?.slower && stage === "goal" && <p className={styles.tvTag}>Again, slower</p>}
      </section>

      <aside className={styles.story} data-field={look[stage].field} aria-live="polite">
        <ol className={styles.dots} aria-label={`Step ${STAGES.indexOf(stage) + 1} of ${STAGES.length}`}>
          {STAGES.map((s, i) => (
            <li key={s} data-state={i < STAGES.indexOf(stage) ? "done" : s === stage ? "now" : undefined} />
          ))}
        </ol>
        <div className={styles.storyArt} key={stage}>
          <Pip pose={look[stage].pip} size={112} />
        </div>
        <h1 className={styles.storyTitle}>{beat.title}</h1>
        <p className={styles.storyLine}>{beat.line}</p>

        {stage === "sofa" && (
          <div className={styles.picker}>
            <p className={styles.pickerLabel}>Which one are you?</p>
            <ul>
              {fans.map((fan) => (
                <li key={fan.id}>
                  <button
                    type="button"
                    aria-pressed={me === fan.id}
                    onClick={() => setMe((m) => (m === fan.id ? null : fan.id))}
                  >
                    <FanFace id={fan.id as CastId} size={52} />
                    <span>{fan.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {stage === "goal" && latestStep?.type === "step" && (
          <p className={styles.working} key={`${latestStep.role}-${latestStep.state}`}>
            <span className={styles.workingDot} aria-hidden="true" />
            {stepLine(latestStep.role, latestStep.summary)}
          </p>
        )}

        {stage === "asks" && wire && (
          <ul className={styles.asks}>
            {[...wire.candidates]
              .filter((c) => (c.askedBy ?? []).length > 0)
              .sort((a, b) => (b.askedBy?.length ?? 0) - (a.askedBy?.length ?? 0))
              .map((c, i) => (
                <li key={c.candidateId} style={{ animationDelay: `${i * 120}ms` }}>
                  <span className={styles.askers}>
                    {(c.askedBy ?? []).map((id) => (
                      <FanFace key={id} id={id as CastId} size={30} />
                    ))}
                  </span>
                  <strong>{titleOf(c.candidateId)}</strong>
                  <span>{c.askedBy?.length === 1 ? "1 asked" : `${c.askedBy?.length} asked`}</span>
                </li>
              ))}
          </ul>
        )}

        {stage === "pick" && wire && (
          <ul className={styles.picks} data-revealed={revealed || undefined}>
            {[...wire.candidates]
              .filter((c) => c.won || (c.askedBy ?? []).length > 0)
              .sort((a, b) => Number(b.won) - Number(a.won))
              .map((c, i) => (
                <li
                  key={c.candidateId}
                  className={styles.pick}
                  data-won={c.won || undefined}
                  style={{ animationDelay: `${i * 70}ms` }}
                >
                  <strong>{titleOf(c.candidateId)}</strong>
                  <span className={styles.stamp}>
                    {c.won ? "On the TV" : stampFor(wire, c.candidateId, present)}
                  </span>
                </li>
              ))}
          </ul>
        )}

        {stage === "pick" && wire && revealed && waitTipped(wire) && (
          <p className={styles.waited}>{waitTipped(wire)}</p>
        )}

        <div className={styles.actions}>
          {stage === "sofa" && (
            <button
              type="button"
              className={styles.play}
              disabled={join !== "ready"}
              onClick={() => start(false)}
            >
              {join === "joining" ? "Getting the sofa ready…" : "Play the goal"}
            </button>
          )}
          {stage === "goal" && decision && goalSeen && (
            <NextButton key="goal" holdMs={2_000} onNext={advance} />
          )}
          {stage === "goal" && !(decision && goalSeen) && (
            <p className={styles.waiting}>{goalSeen ? "The helpers are asking…" : "Watch the replay"}</p>
          )}
          {stage === "asks" && (
            <NextButton
              key="asks"
              holdMs={holdFor(beat.title, beat.line) + 250 * asks.size}
              onNext={advance}
            />
          )}
          {stage === "pick" && (
            <NextButton key="pick" holdMs={holdFor(beat.title, beat.line) + 2_200} onNext={advance} />
          )}
          {allLit && (
            <>
              <button type="button" className={styles.again} onClick={() => start()}>
                Play it again
              </button>
              <button
                type="button"
                className={styles.tea}
                aria-pressed={away}
                onClick={() => {
                  setAway(!away);
                  start(!away);
                }}
              >
                {away ? "Ana's back from the kitchen" : "What if Ana goes to make tea?"}
              </button>
              <a className={styles.try} href={`/join?room=${room}&live=1`}>
                Try it yourself: set up your own helper
              </a>
            </>
          )}
        </div>
        {join === "failed" && (
          <p className={styles.error}>The room server isn't answering. Try again in a moment.</p>
        )}
      </aside>

      <section className={styles.phones} aria-label="The phones">
        {fans.map((fan) => {
          const here = present.includes(fan);
          const order = present.indexOf(fan);
          const on = stage === "phones" && here && lit > order;
          const ask = asks.get(fan.id);
          const privately = wire?.deliveredPrivately.find((d) => d.agentId === fan.id);
          return (
            <div
              key={fan.id}
              className={styles.fan}
              data-mine={me === fan.id || undefined}
              data-lit={on || undefined}
              data-away={!here || undefined}
              data-cast={fan.id}
            >
              <p className={styles.fanName}>
                <FanFace id={fan.id as CastId} size={40} />
                <span>
                  {fan.name}
                  <small>
                    {!here
                      ? "Making tea"
                      : on && wire
                        ? gotLine(wire, fan.id)
                        : `${fan.club === "kestrel" ? "Kestrel" : "Ashvale"} fan`}
                  </small>
                </span>
              </p>
              <div className={styles.phoneWrap}>
                <Scaled width={414} height={868} className={styles.phone}>
                  <FanPhone
                    fan={fan}
                    waiting={!on}
                    {...(here && tokens[fan.id] ? { token: tokens[fan.id] } : {})}
                  />
                </Scaled>
                <Bubble
                  fan={fan}
                  stage={stage}
                  here={here}
                  on={on}
                  sad={unhappy(present).includes(fan)}
                  {...(ask ? { ask } : {})}
                  {...(privately && stage === "phones" && !on
                    ? { coming: titleOf(privately.candidateId) }
                    : {})}
                />
                {allLit && me === fan.id && <span className={styles.yours}>Here's yours</span>}
              </div>
            </div>
          );
        })}
      </section>
    </main>
  );
}

interface BubbleProps {
  fan: Fan;
  stage: Stage;
  here: boolean;
  on: boolean;
  sad: boolean;
  ask?: string;
  coming?: string;
}

/** What shows over a phone before it lights up: the fan's own words, then the helper's ask, then what's coming. */
function Bubble({ fan, stage, here, on, sad, ask, coming }: BubbleProps) {
  if (!here) return <p className={styles.bubble}>Back in a minute</p>;
  if (on) return null;
  if (coming) {
    return (
      <p className={styles.chip}>
        <span aria-hidden="true">●</span> For {fan.name}, after the TV: {coming}
      </p>
    );
  }
  if (stage === "sofa") return <p className={styles.bubble}>“{fan.told}”</p>;
  if (stage === "goal") {
    return sad ? (
      <p className={styles.bubble}>Ay, no.</p>
    ) : (
      <p className={styles.helperBubble}>
        <Helper id={fan.id as CastId} size={34} />
        <span className={styles.typing} role="img" aria-label="Typing">
          <i />
          <i />
          <i />
        </span>
      </p>
    );
  }
  if (ask && (stage === "asks" || stage === "pick")) {
    return (
      <p className={styles.helperBubble}>
        <Helper id={fan.id as CastId} size={34} />
        <span>{askLine(fan, ask)}</span>
      </p>
    );
  }
  return null;
}

/** The words for each beat. */
function copyFor(stage: Stage, wire: Decision | undefined, present: Fan[], winnerId: string | undefined) {
  const outsiders = outnumbered(present);
  switch (stage) {
    case "sofa":
      return {
        title: "Four fans, one TV",
        line: outsiders.length
          ? `${listNames(outsiders.map((f) => f.name))} is the only Ashvale fan on the sofa. Everyone has their own helper on their phone.`
          : "Everyone has their own helper on their phone.",
      };
    case "goal":
      return {
        title: "Okafor scores!",
        line: unhappy(present).length
          ? `Kestrel go 5–1 up. ${listNames(unhappy(present).map((f) => f.name))} is not happy about it.`
          : "Kestrel go 5–1 up, and the whole sofa is on its feet.",
      };
    case "asks":
      return {
        title: "Everyone wants the TV",
        line: "There's room for one thing on the TV.",
      };
    case "pick":
      return {
        title: winnerId ? `Pip picks “${titleOf(winnerId)}”` : "Pip keeps the TV clear",
        line: wire ? whyItWon(wire, present) : "",
      };
    case "phones":
      return {
        title: "The rest go to phones",
        line: "Every pick that missed the TV shows up on its fan's phone, once the TV has shown its pick.",
      };
  }
}

/** What the TV's lower third says: the agents' write-up when the TV shows where it started, else the pick. */
function tvOverlay(
  wire: Decision,
  winnerId: string,
  writeUp: Record<string, string> | undefined,
  present: Fan[],
): Overlay {
  const winner = wire.candidates.find((c) => c.candidateId === winnerId);
  const askers = winner?.askedBy ?? [];
  const neutral = !candidates[winnerId]?.favours;
  const base = { asked: askers.length, inRoom: present.length, neutral };
  if (winnerId === "where-it-started" && writeUp?.en_headline) {
    return { ...base, headline: writeUp.en_headline, line: writeUp.en_line ?? "" };
  }
  if (winnerId === "where-it-started")
    return { ...base, headline: goal.copy.en_headline, line: goal.copy.en_line };
  return {
    ...base,
    headline: titleOf(winnerId),
    line: `${listNames(askers.map((id) => fans.find((f) => f.id === id)?.name ?? id))} asked for this one.`,
  };
}
