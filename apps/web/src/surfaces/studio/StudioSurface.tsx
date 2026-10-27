import { Wordmark } from "@frontroom/design";
import ashvale from "@frontroom/design/crests/ashvale.svg";
import kestrel from "@frontroom/design/crests/kestrel.svg";
import { useEffect, useState } from "react";
import { goal, scoreText } from "../../fixtures/goal";
import { clubs } from "../../fixtures/room";
import { Audience } from "./Audience";
import { DemandRace, type Suggestion } from "./DemandRace";
import { Drawer } from "./Drawer";
import { LiveCue, type Withdrawal } from "./LiveCue";
import { MatchLane } from "./MatchLane";
import styles from "./StudioSurface.module.css";
import {
  count,
  cues,
  type Demand,
  type Destination,
  demand,
  followed,
  LIVE_CUE,
  languages,
  MATCH_CLOCK,
  plus,
  rollout,
  type StudioCue,
  sofa,
  watchStyle,
} from "./studio-fixture";
import { useTick } from "./useTick";

const destinations: { id: Destination; label: string; line: string }[] = [
  {
    id: "all",
    label: "All rooms",
    line: "Every room gets it, and each room decides whether it goes on the TV.",
  },
  {
    id: "one-club",
    label: "One club's rooms",
    line: "Only rooms where every fan supports one club. Mixed rooms still get it on phones.",
  },
  { id: "language", label: "By language", line: "Only rooms whose captions are in a ready language." },
];

interface Toast {
  id: number;
  text: string;
}

/**
 * The broadcaster's screen during a match: the cue on TVs and what it did in the rooms, what rooms are asking
 * for right now (including what the studio has no cue for), and who is watching. The producer sends each
 * moment once; every living room decides how to show it.
 */
export function StudioSurface() {
  const t = useTick();
  const clock = plus(MATCH_CLOCK, t);
  const minute = Number(clock.split(":")[0]);
  const [withdrawn, setWithdrawn] = useState<Withdrawal | null>(null);
  const [made, setMade] = useState<StudioCue | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [drawer, setDrawer] = useState<"facts" | "where" | null>(null);
  const [destination, setDestination] = useState<Destination>("all");
  const [toasts, setToasts] = useState<Toast[]>([]);

  const live = cues.find((c) => c.id === LIVE_CUE) ?? cues[0];
  const lane = [
    ...cues.map((c) => (c.id === LIVE_CUE && withdrawn ? { ...c, state: "withdrawn" as const } : c)),
    ...(made ? [made] : []),
  ];
  const r = rollout(t);
  const asks = demand(t, made !== null).map((d) =>
    withdrawn && d.answer === "on-tvs" ? { ...d, answer: "withdrawn" as const } : d,
  );

  const toast = (text: string) => {
    const id = Date.now();
    setToasts([{ id, text }]);
  };
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = window.setTimeout(() => setToasts((all) => all.slice(1)), 6000);
    return () => window.clearTimeout(timer);
  }, [toasts]);

  const withdraw = (w: Withdrawal) => {
    setWithdrawn(w);
    toast(`Pulled from ${count(w.tvs)} TVs and ${count(w.phones)} phones. Correction sent.`);
  };
  const make = (item: Demand) => {
    setMade({
      id: `made-${item.id}`,
      minute: clock,
      title: item.title,
      kind: "From what rooms asked",
      state: "drafted",
      note: "Needs a check before it can air",
      languages: [],
      facts: [],
    });
    toast(`Drafted "${item.title}". It's in the cues, waiting for a check.`);
  };
  const suggest = (top: Demand) => {
    setSuggestion({ title: top.title, rooms: top.asks, at: clock });
    toast(`Sent to the gallery: ${top.title}, asked for in ${count(top.asks)} rooms.`);
  };

  if (!live) return null;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <a href="/" className={styles.home}>
          <Wordmark variant="lockup" height={24} />
        </a>
        <p className={styles.product}>Studio</p>
        <p className={styles.match}>
          <img className={styles.crest} src={kestrel} alt="" />
          <span>{clubs.kestrel.short}</span>
          <span className={styles.score}>{scoreText(goal.scoreAfter)}</span>
          <span>{clubs.ashvale.short}</span>
          <img className={styles.crest} src={ashvale} alt="" />
          <span className={styles.clock}>{clock}</span>
        </p>
        <p className={styles.tally}>
          <span className={styles.live}>Live</span>
          in {count(r.rooms)} rooms
        </p>
        <p className={styles.behind}>Rooms run 38 s behind live, on average</p>
        <p className={styles.simulated}>Simulated rollout over a made-up league</p>
      </header>

      <div className={styles.grid}>
        <LiveCue
          cue={live}
          t={t}
          clock={clock}
          withdrawn={withdrawn}
          onWithdraw={withdraw}
          onFacts={() => setDrawer("facts")}
          onWhere={() => setDrawer("where")}
        />
        <DemandRace demand={asks} suggestion={suggestion} onSuggest={suggest} onMake={make} />
        <Audience players={followed(t)} sofa={sofa(t)} watch={watchStyle(t)} captions={languages(t)} />
      </div>

      <MatchLane cues={lane} minute={minute} />

      <Drawer title="Facts on air" open={drawer === "facts"} onClose={() => setDrawer(null)}>
        <p className={styles.drawerLine}>
          Every claim on the TV is matched to the match's event feed before it airs.
        </p>
        <ul className={styles.facts}>
          {live.facts.map((f) => (
            <li key={f.claim} data-model={f.checkedBy === "model" || undefined}>
              <span className={styles.factTag}>
                {f.checkedBy === "feed" ? "Event feed" : "Estimate, off air"}
              </span>
              <strong>{f.claim}</strong>
              <code>{f.sources.join(", ")}</code>
            </li>
          ))}
        </ul>
      </Drawer>

      <Drawer title="Where it goes" open={drawer === "where"} onClose={() => setDrawer(null)}>
        <fieldset className={styles.send}>
          <legend>Send to</legend>
          {destinations.map((d) => (
            <label key={d.id} className={styles.option}>
              <input
                type="radio"
                name="destination"
                checked={destination === d.id}
                onChange={() => setDestination(d.id)}
              />
              <span>
                <strong>{d.label}</strong>
                {d.line}
              </span>
            </label>
          ))}
        </fieldset>
        <div>
          <h3 className={styles.drawerHeading}>Captions</h3>
          <ul className={styles.langs}>
            {live.languages.map((l) => (
              <li key={l.lang}>
                <strong>{l.name}</strong>
                <span>{l.headline ?? "Gets English captions until a checked version exists"}</span>
              </li>
            ))}
          </ul>
        </div>
      </Drawer>

      <ol className={styles.toasts} aria-live="polite">
        {toasts.map((x) => (
          <li key={x.id}>{x.text}</li>
        ))}
      </ol>
    </main>
  );
}
