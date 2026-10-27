import { clubs } from "../../fixtures/room";
import styles from "./Audience.module.css";
import { count, type Followed, PRIVACY_MINIMUM, percent, rooms } from "./studio-fixture";

interface Slice {
  id: string;
  label: string;
  n: number;
  colour: string;
}

interface AudienceProps {
  players: Followed[];
  sofa: Slice[];
  watch: Slice[];
  captions: Slice[];
}

/** Who is watching and whom they follow: counts of what helpers asked for, never what a fan said. */
export function Audience({ players, sofa, watch, captions }: AudienceProps) {
  return (
    <section className={styles.panel} aria-labelledby="audience">
      <h2 id="audience" className={styles.title}>
        Players fans follow
      </h2>
      <ol className={styles.players}>
        {players.map((p) => (
          <li key={`${p.club}-${p.number}`} className={styles.player}>
            <span
              className={styles.shirt}
              style={{ background: clubs[p.club].colour, color: clubs[p.club].onColour }}
              role="img"
              aria-label={`${clubs[p.club].name}, number ${p.number}`}
            >
              {p.number}
            </span>
            <span className={styles.who}>
              {p.name}
              <small>{clubs[p.club].short}</small>
            </span>
            <span className={styles.follows}>{count(p.follows)}</span>
            <span className={styles.since} data-flat={p.since < 100 || undefined}>
              {p.since < 100 ? "steady" : `+${count(p.since)} since the goal`}
            </span>
          </li>
        ))}
      </ol>

      <h2 className={styles.title}>Who's watching</h2>
      <Mix label="On the sofa" unit="rooms" slices={sofa} />
      <Mix label="How fans watch" unit="fans" slices={watch} />
      <Mix label="Captions" unit="rooms" slices={captions} />
      <p className={styles.privacy}>
        Counts of what helpers asked for. Nobody here sees what a fan told their helper, and groups under{" "}
        {PRIVACY_MINIMUM} rooms stay hidden.
      </p>
    </section>
  );
}

function Mix({ label, unit, slices }: { label: string; unit: string; slices: Slice[] }) {
  const total = slices.reduce((sum, s) => sum + s.n, 0);
  const shown = slices.filter((s) => s.n >= PRIVACY_MINIMUM);
  const hidden = slices.filter((s) => s.n < PRIVACY_MINIMUM);
  return (
    <div className={styles.mix}>
      <p className={styles.mixLabel}>{label}</p>
      <div
        className={styles.bar}
        role="img"
        aria-label={`${label}: ${shown.map((s) => `${s.label} ${percent(s.n, total)}%`).join(", ")}`}
      >
        {shown.map((s) => (
          <span key={s.id} style={{ flexGrow: s.n, background: s.colour }} />
        ))}
      </div>
      <ul className={styles.legend}>
        {shown.map((s) => (
          <li key={s.id} title={`${count(s.n)} ${unit}`}>
            <i style={{ background: s.colour }} />
            {s.label} <strong>{percent(s.n, total)}%</strong>
          </li>
        ))}
        {hidden.map((s) => (
          <li key={s.id} className={styles.hidden}>
            {s.label}: {rooms(s.n)} {unit}
          </li>
        ))}
      </ul>
    </div>
  );
}
