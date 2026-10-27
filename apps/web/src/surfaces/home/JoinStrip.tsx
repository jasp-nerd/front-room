import { Scaled } from "../../ui/Scaled";
import { JoinPhone } from "../phone/JoinPhone";
import styles from "./JoinStrip.module.css";

/** The real join screens, at the steps that show what you can set. They are pictures here: /join is live. */
const steps = [
  { step: 1, caption: "Scan the code on the TV, or type the room number." },
  { step: 2, caption: "Say how you like to watch, and in which language." },
  { step: 3, caption: "Follow a player or two, from either club." },
  { step: 5, caption: "Check what your helper understood. Change it any time." },
];

/** Inert, so the screens can't be tabbed into or tapped: the real flow is one click away. */
const inert = (element: HTMLElement | null) => element?.setAttribute("inert", "");

export function JoinStrip() {
  return (
    <section className={styles.join} aria-labelledby="join">
      <div className={styles.intro}>
        <h2 id="join" className={styles.title}>
          Joining takes about a minute
        </h2>
        <p className={styles.lede}>
          No app and no account. You answer a few taps on your phone and your helper is set up for the match.
        </p>
        <a className={styles.try} href="/join?room=4821">
          Try it on your phone
        </a>
      </div>
      <ol className={styles.steps}>
        {steps.map(({ step, caption }) => (
          <li key={step} className={styles.step}>
            <div ref={inert} className={styles.screen}>
              <Scaled width={414} height={868}>
                <JoinPhone room="4821" step={step} />
              </Scaled>
            </div>
            <p className={styles.caption}>{caption}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
