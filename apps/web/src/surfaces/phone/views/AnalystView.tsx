import type { CastId } from "@frontroom/design";
import {
  clip,
  decisive,
  firstPress,
  frameAtClock,
  goal,
  scorer,
  secondHalfClock,
} from "../../../fixtures/goal";
import { kits } from "../../../fixtures/room";
import { looks } from "../../../match/clip";
import { type Arrow, TopDownPitch } from "../../../match/TopDownPitch";
import { copy } from "../copy";
import { HelperTag } from "./HelperTag";
import { ScoreLine } from "./ScoreLine";
import chain from "./ValueChain.module.css";
import styles from "./views.module.css";

/** The moment Mensah pressed, from the engine's tracking: who was where, and where each press went. */
const pressFrame = frameAtClock(firstPress.clockMs);
const presses = goal.chain.filter((a) => a.type === "press");
const playerOf = (name: string) => clip.players.find((p) => p.side === "home" && p.name === name)?.id;
const pressing: Arrow[] = presses.flatMap((press) => {
  const presser = pressFrame.players.find((p) => p.playerId === playerOf(press.player));
  return presser && press.end ? [{ from: presser, to: press.end, kind: "press" as const }] : [];
});
const lund = clip.players.find((p) => p.name === "Lund")?.id ?? "";
const pressers = [...presses.map((p) => playerOf(p.player) ?? ""), lund];

/** The three actions that moved the chance most, kept in match order. The shot is priced separately, as xG. */
const shown = goal.chain
  .filter((a) => a.type !== "shot")
  .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
  .slice(0, 3)
  .sort((a, b) => a.clockMs - b.clockMs);
const largest = Math.max(...shown.map((a) => Math.abs(a.value)));
const signed = (value: number) => `${value < 0 ? "−" : "+"}${Math.abs(value).toFixed(3)}`;

/**
 * The analyst's lens: the shape and the numbers, delivered privately when the room picked something else.
 * Values are possession value added: how much each action changed the chance of a goal against what a
 * typical player would have done from the same spot.
 */
/**
 * The analyst lens. When the room sent Kestrel's pressing map to this phone, that leads; when this fan's pick
 * is the one on the TV, the TV's story leads instead, with the same pressing picture and the numbers.
 */
export function AnalystView({ fan, ownPick }: { fan: CastId; ownPick?: string }) {
  const pressingMap = ownPick === "kestrel-pressing-map";
  const call =
    // The value model's view is an estimate, and the phone says so: graded against the simulator's ground
    // truth it is a useful hint, not a verdict (agents/frontroom_agents/evals/origins.py).
    `Model estimate: ${decisive.label} added the most. A hint, not a verdict.`;
  return (
    <div className={styles.content}>
      <ScoreLine />
      <section className={styles.block}>
        <HelperTag fan={fan}>{pressingMap ? copy.en.fromHelper : copy.en.onTvYourWay}</HelperTag>
        <h2 className={styles.headline}>{pressingMap ? "Kestrel's pressing map" : goal.copy.en_headline}</h2>
        <div className={styles.pitchCard}>
          <TopDownPitch
            frame={pressFrame}
            players={looks(clip)}
            kits={kits}
            arrows={pressing}
            focus={pressers}
            crop={{ x0: 38, x1: 80, y0: 36, y1: 62 }}
            title={`${presses.map((p) => p.player).join(" and ")} closing down Lund on halfway at ${secondHalfClock(firstPress.clockMs)}`}
          />
        </div>
      </section>
      <section className={styles.block}>
        <h3 className={chain.heading}>
          <span className={styles.title}>How the chance built</span>
          <span className={chain.unit}>Value added</span>
        </h3>
        <table className={chain.table}>
          <tbody>
            {shown.map((action) => (
              <tr key={action.id}>
                <th scope="row" className={chain.who}>
                  {action.player}
                </th>
                <td className={chain.what}>{action.label.split("'s ")[1]}</td>
                <td className={chain.bar} aria-hidden="true">
                  <span style={{ width: `${(Math.abs(action.value) / largest) * 100}%` }} />
                </td>
                <td className={chain.value}>{signed(action.value)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className={chain.who}>
                {scorer}
              </th>
              <td className={chain.what}>Shot, xG</td>
              <td className={chain.bar} />
              <td className={chain.value}>{goal.shotXg.toFixed(2)}</td>
            </tr>
          </tfoot>
        </table>
        <p className={styles.lede}>{call}</p>
        <p className={styles.note}>
          The match is simulated. Only the value model learned from real data (public Wyscout 2017/18 events).
        </p>
      </section>
    </div>
  );
}
