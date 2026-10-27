import { type CastId, FanFace, Helper, Pip, Wordmark } from "@frontroom/design";
import { useEffect, useState } from "react";
import { CODE_URL, VIDEO_URL } from "../../links";
import { Scaled } from "../../ui/Scaled";
import { boardSize, PhonesBoard } from "../phone/PhonesBoard";
import { HeroRoom } from "./HeroRoom";
import styles from "./HomeSurface.module.css";
import { JoinStrip } from "./JoinStrip";
import { PickStory } from "./PickStory";
import { RoomTrace } from "./RoomTrace";

/** The demo family, as the step art shows them. */
const cast: CastId[] = ["rob", "ana", "leo", "sam"];

const rules = [
  "Nothing one-sided while both clubs are on the sofa.",
  "Whoever has waited longest counts a bit more.",
  "Nothing reaches a phone before the TV.",
];

/** The front door: what Front Room is, shown more than told, with the details one click away on /how. */
export function HomeSurface() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <a href="/" aria-label="Front Room, home">
          <Wordmark variant="lockup" height={24} />
        </a>
        <nav className={styles.nav} aria-label="Pages">
          <a href="/how">How it works</a>
          <a href={VIDEO_URL} target="_blank" rel="noopener">
            Video
          </a>
          <a href={CODE_URL} target="_blank" rel="noopener">
            Code
          </a>
          <a className={styles.navButton} href="/demo?live=1">
            Watch a goal
          </a>
        </nav>
      </header>

      <main>
        <section className={styles.hero}>
          <div className={styles.heroText}>
            <p className={styles.eyebrow}>A match-day feature for football broadcasts</p>
            <h1 className={styles.headline}>Who gets the TV when a goal goes in?</h1>
            <p className={styles.lede}>
              Each fan's AI helper asks for the screen. Pip picks one that's fair to both clubs, and every
              other pick goes to that fan's phone.
            </p>
            <div className={styles.actions}>
              <a className={styles.primary} href="/demo?live=1">
                Watch a goal
              </a>
              <a className={styles.secondary} href="/how">
                How it works
              </a>
            </div>
          </div>
          <HeroRoom />
          <RoomTrace />
        </section>

        <section className={styles.section} aria-labelledby="how">
          <h2 id="how" className={styles.title}>
            How it works
          </h2>
          <ol className={styles.steps}>
            <li className={styles.step} data-field="sky">
              <div className={styles.stepArt}>
                {cast.map((id) => (
                  <FanFace key={id} id={id} size={92} />
                ))}
              </div>
              <span className={styles.stepNumber}>1</span>
              <h3 className={styles.stepTitle}>Everyone gets their own helper</h3>
              <p>An AI on your phone. Tell it how you watch: the numbers, simple, in Spanish, read aloud.</p>
            </li>
            <li className={styles.step} data-field="sun">
              <div className={styles.stepArt}>
                {cast.map((id) => (
                  <Helper key={id} id={id} size={96} />
                ))}
              </div>
              <span className={styles.stepNumber}>2</span>
              <h3 className={styles.stepTitle}>A goal! Every helper wants something</h3>
              <p>Rob's wants the pressing map. Ana's wants the keeper's view. Only one fits on the TV.</p>
            </li>
            <li className={styles.step} data-field="pitch">
              <div className={styles.stepArt}>
                <Pip pose="whistle" size={120} />
              </div>
              <span className={styles.stepNumber}>3</span>
              <h3 className={styles.stepTitle}>Pip, the referee, picks</h3>
              <p>Something fair to both teams goes on the TV. Everything else goes to its own phone.</p>
            </li>
          </ol>
        </section>

        <JoinStrip />

        <section className={styles.section} aria-labelledby="four">
          <div className={styles.titleRow}>
            <h2 id="four" className={styles.title}>
              What each phone showed for the same goal
            </h2>
            <a className={styles.link} href="/phones">
              See the phones full screen
            </a>
          </div>
          <PhonesOnHome />
        </section>

        <section className={styles.fair} aria-labelledby="fair">
          <div className={styles.fairText}>
            <Pip pose="whistle" size={150} className={styles.fairPip} />
            <h2 id="fair" className={styles.title}>
              Pip keeps it fair
            </h2>
            <p className={styles.fairLine}>
              Rob supports Kestrel. Ana supports Ashvale. So when Kestrel score, the TV won't rub it in. Rob's
              phone gets the Kestrel pressing map instead.
            </p>
            <ul className={styles.rules}>
              {rules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </div>
          <div className={styles.decision}>
            <PickStory />
          </div>
        </section>

        <section className={styles.section} aria-labelledby="studio">
          <div className={styles.studio}>
            <div>
              <h2 id="studio" className={styles.title}>
                For the broadcaster
              </h2>
              <p className={styles.body}>
                The studio sends each moment once, and every living room decides how to show it. The
                broadcaster sees what rooms are asking for as the match goes on, never who asked.
              </p>
              <a className={styles.link} href="/studio">
                Open the studio
              </a>
            </div>
            <div className={styles.built}>
              <h2 className={styles.smallTitle}>What it runs on</h2>
              <ul className={styles.stack}>
                <li>Microsoft Foundry</li>
                <li>Microsoft Agent Framework</li>
                <li>A2A and MCP</li>
                <li>Azure Cosmos DB</li>
                <li>Azure Event Hubs</li>
                <li>Content Safety and Speech</li>
                <li>Azure Container Apps</li>
                <li>GitHub Actions</li>
              </ul>
              <p className={styles.small}>
                A team of AI agents: one helper per fan, investigators for each goal and Pip, the referee,
                which talks to the helpers over A2A.
              </p>
              <a className={styles.link} href="/how">
                How it's built
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <Wordmark variant="lockup" height={18} />
        <p>
          A made-up league: Kestrel FC, Ashvale Athletic and every player are fictional. Built for the
          Microsoft × Premier League Inside the Game hackathon.
        </p>
        <nav className={styles.footerNav} aria-label="More">
          <a href="/demo?live=1">Watch a goal</a>
          <a href={VIDEO_URL}>The video</a>
          <a href={CODE_URL}>The code</a>
          <a href="/join?room=4821">Join a room</a>
          <a href="/phones">The four phones</a>
          <a href="/tv?state=join">The TV before kick-off</a>
          <a href="/studio">The studio</a>
          <a href="/how">How it works</a>
        </nav>
      </footer>
    </div>
  );
}

/** The phones board, four across, or two by two on a narrow screen, scaled to the section's width. */
function PhonesOnHome() {
  const narrow = useNarrow();
  const columns = narrow ? 2 : 4;
  return (
    <Scaled {...boardSize[columns]} className={styles.board}>
      <PhonesBoard columns={columns} />
    </Scaled>
  );
}

function useNarrow(): boolean {
  const query = "(max-width: 760px)";
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const list = window.matchMedia(query);
    const change = () => setNarrow(list.matches);
    list.addEventListener("change", change);
    return () => list.removeEventListener("change", change);
  }, []);
  return narrow;
}
