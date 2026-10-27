import { Button, Helper, PhoneFrame, Pip } from "@frontroom/design";
import { useState } from "react";
import { followable, type Metric, metricNames } from "../../fixtures/stats";
import { liveRoom, serverUrl } from "../../live/feed";
import styles from "./JoinPhone.module.css";

/** The ways to watch a helper can be set to. Each is one of the four lenses the phones show. */
const ways = [
  { id: "numbers", label: "Show me the numbers", hint: "Shapes, stats, who did what" },
  { id: "simple", label: "Keep it simple", hint: "Just the big moments" },
  { id: "kid", label: "I'm a kid", hint: "Fun facts and things to spot" },
  { id: "listen", label: "I'd rather listen", hint: "Told in your earbuds" },
] as const;

type Way = (typeof ways)[number]["id"];
type Lang = "en" | "es";

const metrics = Object.keys(metricNames.en) as Metric[];

const STEPS = 6;

/**
 * Joining a room from the QR code on the TV, one question per screen: join, how you watch, who you follow,
 * your one number, what your helper understood, done. `/join?room=4821&step=3` opens a step directly, for
 * screenshots and the video. The demo fan is Ana: simple, in Spanish, Ashvale's possession, so those are the
 * starting answers.
 */
export function JoinPhone({ room, step: firstStep = 1 }: { room: string; step?: number }) {
  const [step, setStep] = useState(Math.min(Math.max(firstStep, 1), STEPS));
  const [way, setWay] = useState<Way>("simple");
  const [lang, setLang] = useState<Lang>("es");
  const [follows, setFollows] = useState<string[]>([]);
  const [metric, setMetric] = useState<Metric | null>("possession");
  const [problem, setProblem] = useState<string | null>(null);
  const next = () => setStep((s) => Math.min(s + 1, STEPS));
  const back = () => setStep((s) => Math.max(s - 1, 1));

  // Following a real room (`?live=1`), "Looks right" joins it: the answers go to the server as one plain
  // sentence, which Content Safety screens and the profiler turns into the helper's profile.
  async function join() {
    const room = liveRoom();
    if (!room) return next();
    setProblem(null);
    const response = await fetch(serverUrl(`/rooms/${room}/fans`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fan: guestId(), told: inWords(way, lang, follows, metric) }),
    }).catch(() => null);
    if (response?.ok) return next();
    const detail = response ? ((await response.json()) as { detail?: unknown }).detail : undefined;
    setProblem(typeof detail === "string" ? detail : "Couldn't reach the room. Try again in a moment.");
  }

  return (
    <PhoneFrame time="19:52" lang="en" accent="sun">
      <div className={styles.top}>
        {step > 1 && step < STEPS ? (
          <button type="button" className={styles.back} onClick={back}>
            Back
          </button>
        ) : (
          <span />
        )}
        <span className={styles.dots} role="img" aria-label={`Step ${step} of ${STEPS}`}>
          {Array.from({ length: STEPS }, (_, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: the dots are positions, fixed in number.
            <i key={i} data-state={i + 1 < step ? "done" : i + 1 === step ? "now" : undefined} />
          ))}
        </span>
      </div>
      {step === 1 && <Hello room={room} onNext={next} />}
      {step === 2 && <HowYouWatch way={way} lang={lang} onWay={setWay} onLang={setLang} onNext={next} />}
      {step === 3 && <Follow follows={follows} onFollows={setFollows} onNext={next} />}
      {step === 4 && <OneNumber metric={metric} onMetric={setMetric} onNext={next} />}
      {step === 5 && (
        <Understood way={way} lang={lang} follows={follows} metric={metric} problem={problem} onNext={join} />
      )}
      {step === 6 && <Ready room={room} />}
    </PhoneFrame>
  );
}

function Hello({ room, onNext }: { room: string; onNext: () => void }) {
  return (
    <>
      <div className={styles.content}>
        <div className={styles.field} data-colour="sun">
          <Pip pose="wave" size={230} />
        </div>
        <h1 className={styles.question}>Join room {room}</h1>
        <p className={styles.lede}>
          Everyone on the sofa gets a helper. Yours asks the TV for what you like.
        </p>
      </div>
      <div className={styles.actions}>
        <Button variant="join" block onClick={onNext}>
          Join the room
        </Button>
        <p className={styles.small}>Under 13? A grown-up joins for you.</p>
      </div>
    </>
  );
}

function HowYouWatch({
  way,
  lang,
  onWay,
  onLang,
  onNext,
}: {
  way: Way;
  lang: Lang;
  onWay: (way: Way) => void;
  onLang: (lang: Lang) => void;
  onNext: () => void;
}) {
  return (
    <>
      <div className={styles.content}>
        <h1 className={styles.question}>How do you like to watch?</h1>
        <fieldset className={styles.choices}>
          <legend className={styles.hidden}>How you like to watch</legend>
          {ways.map((w) => (
            <label key={w.id} className={styles.choice}>
              <input
                type="radio"
                name="way"
                value={w.id}
                checked={way === w.id}
                onChange={() => onWay(w.id)}
              />
              <span>
                <strong>{w.label}</strong>
                <span>{w.hint}</span>
              </span>
              <i className={styles.tick} aria-hidden="true" />
            </label>
          ))}
        </fieldset>
        <fieldset className={styles.language}>
          <legend className={styles.label}>On your phone, in</legend>
          {(
            [
              ["en", "English"],
              ["es", "Español"],
            ] as const
          ).map(([id, name]) => (
            <label key={id} className={styles.segment}>
              <input type="radio" name="lang" value={id} checked={lang === id} onChange={() => onLang(id)} />
              {name}
            </label>
          ))}
        </fieldset>
      </div>
      <div className={styles.actions}>
        <Button block onClick={onNext}>
          Next
        </Button>
      </div>
    </>
  );
}

/** Players from both clubs, home first; following nobody means just the team. */
function Follow({
  follows,
  onFollows,
  onNext,
}: {
  follows: string[];
  onFollows: (follows: string[]) => void;
  onNext: () => void;
}) {
  const toggle = (label: string) =>
    onFollows(follows.includes(label) ? follows.filter((f) => f !== label) : [...follows, label]);
  return (
    <>
      <div className={styles.content}>
        <h1 className={styles.question}>Anyone you follow?</h1>
        {(["home", "away"] as const).map((side) => (
          <fieldset key={side} className={styles.chips}>
            <legend className={styles.label}>{side === "home" ? "Kestrel" : "Ashvale"}</legend>
            {followable
              .filter((p) => p.side === side)
              .map((p) => (
                <label key={p.label} className={styles.chip}>
                  <input
                    type="checkbox"
                    checked={follows.includes(p.label)}
                    onChange={() => toggle(p.label)}
                  />
                  {p.label}
                </label>
              ))}
          </fieldset>
        ))}
        <label className={styles.chip} data-wide>
          <input type="checkbox" checked={follows.length === 0} onChange={() => onFollows([])} />
          Just the team
        </label>
      </div>
      <div className={styles.actions}>
        <Button block onClick={onNext}>
          Next
        </Button>
      </div>
    </>
  );
}

/** The one number the phone keeps in view, measured from the match. */
function OneNumber({
  metric,
  onMetric,
  onNext,
}: {
  metric: Metric | null;
  onMetric: (metric: Metric | null) => void;
  onNext: () => void;
}) {
  return (
    <>
      <div className={styles.content}>
        <h1 className={styles.question}>One number you care about?</h1>
        <fieldset className={styles.choices}>
          <legend className={styles.hidden}>One number to keep in view</legend>
          {[...metrics, null].map((m) => (
            <label key={m ?? "none"} className={styles.choice} data-compact>
              <input type="radio" name="metric" checked={metric === m} onChange={() => onMetric(m)} />
              <span>
                <strong>{m ? metricNames.en[m] : "No number, thanks"}</strong>
              </span>
              <i className={styles.tick} aria-hidden="true" />
            </label>
          ))}
        </fieldset>
      </div>
      <div className={styles.actions}>
        <Button block onClick={onNext}>
          Next
        </Button>
      </div>
    </>
  );
}

/** A guest's id in the room: short, random, and valid for the server's fan ids. */
const guestId = () => `guest-${Math.random().toString(36).slice(2, 8)}`;

/** The answers as the fan might have said them, which is what the helper's profiler reads. */
function inWords(way: Way, lang: Lang, follows: string[], metric: Metric | null): string {
  return [
    ways.find((w) => w.id === way)?.label,
    lang === "es" ? "In Spanish" : "In English",
    follows.length ? `I follow ${follows.join(" and ")}` : undefined,
    metric ? `My number is ${metricNames.en[metric].toLowerCase()}` : undefined,
  ]
    .filter(Boolean)
    .join(". ");
}

function Understood({
  way,
  lang,
  follows,
  metric,
  problem,
  onNext,
}: {
  way: Way;
  lang: Lang;
  follows: string[];
  metric: Metric | null;
  problem: string | null;
  onNext: () => void;
}) {
  const spanish = lang === "es";
  const asks = [
    ways.find((w) => w.id === way)?.label ?? "",
    spanish ? "Spanish on your phone" : "English on your phone",
    ...(spanish ? ["Spanish captions on the TV"] : []),
    ...(follows.length ? [`Follow ${follows.join(" and ")}`] : []),
    ...(metric ? [`Keep ${metricNames.en[metric].toLowerCase()} in view`] : []),
  ];
  return (
    <>
      <div className={styles.content}>
        <div className={styles.helperRow}>
          <Helper id="ana" size={120} />
          <h1 className={styles.question}>Your helper got it</h1>
        </div>
        <ul className={styles.asks}>
          {asks.map((ask) => (
            <li key={ask}>
              <i className={styles.tick} data-on aria-hidden="true" />
              {ask}
            </li>
          ))}
        </ul>
        <p className={styles.note}>
          When something happens, it asks the TV for these. Only your helper knows what you said; Pip sees
          what it asks for, never why.
        </p>
        {problem && (
          <p className={styles.problem} role="alert">
            {problem}
          </p>
        )}
      </div>
      <div className={styles.actions}>
        <Button block onClick={onNext}>
          Looks right
        </Button>
      </div>
    </>
  );
}

function Ready({ room }: { room: string }) {
  return (
    <div className={styles.content}>
      <div className={styles.field} data-colour="pitch">
        <Pip pose="cheer" size={230} />
      </div>
      <h1 className={styles.question}>You're in!</h1>
      <p className={styles.lede}>
        Watch the TV. Anything your helper finds that the TV doesn't show lands here.
      </p>
      <p className={styles.room}>Room {room}</p>
    </div>
  );
}
