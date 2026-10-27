import { type CastId, Pip } from "@frontroom/design";
import { goal, regain, scorer } from "../../../fixtures/goal";
import kid from "./KidView.module.css";
import styles from "./views.module.css";

const COUNT = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];

/** The goal in three steps a ten-year-old can follow, from the engine's demo goal. */
const story = [
  `${regain.player} stole the ball`,
  `${COUNT[goal.passes] ?? goal.passes} quick passes`,
  `${scorer} ran through and scored`,
];

/** The kid's lens: Pip cheering, the story in three steps, and something to look for on the TV. */
export function KidView(_: { fan: CastId }) {
  return (
    <div className={styles.content}>
      <section className={kid.picked}>
        <div className={kid.words}>
          <h2 className={kid.headline}>Your pick is on the TV!</h2>
          <p className={kid.lede}>Everyone in the room is watching it now.</p>
        </div>
        <Pip pose="cheer" size={132} className={kid.pip} />
      </section>
      <ol className={kid.story}>
        {story.map((step, i) => (
          <li key={step}>
            <span className={kid.step}>{i + 1}</span>
            {step}
          </li>
        ))}
      </ol>
      <section className={styles.block}>
        <h3 className={styles.title}>Spot it on the TV: which number won the ball back?</h3>
        <div className={kid.choices}>
          {[4, 6, 9].map((n) => (
            <button key={n} type="button" className={kid.choice}>
              {n}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
