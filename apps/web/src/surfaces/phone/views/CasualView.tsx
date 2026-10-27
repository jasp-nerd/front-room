import { type CastId, Switch } from "@frontroom/design";
import { clip, frameAtClock, goal, shot, shotDistance } from "../../../fixtures/goal";
import { copy } from "../copy";
import { HelperTag } from "./HelperTag";
import { ScoreLine } from "./ScoreLine";
import shotStyles from "./ShotView.module.css";
import styles from "./views.module.css";

/**
 * Ashvale's penalty area from above, goal at the top, in metres: x across the goal (0 = centre, negative to
 * the shooter's left), y out from the goal line. Everyone is where the engine's tracking had them when
 * Okafor shot; the ball's line is the shot as the event feed recorded it.
 */
const GOAL_X = shot.end && shot.end.x < 52.5 ? 0 : 105;
const toArea = (p: { x: number; y: number }) =>
  GOAL_X === 0 ? { x: p.y - 34, y: p.x } : { x: 34 - p.y, y: 105 - p.x };

const atShot = frameAtClock(shot.clockMs);
const person = (id: string | undefined) => atShot.players.find((p) => p.playerId === id);
const shooterId = clip.players.find((p) => p.side === "home" && p.name === shot.player)?.id;
const keeperId = clip.players.find((p) => p.side === "away" && p.keeper)?.id;
const SHOOTER = toArea(person(shooterId) ?? shot.start);
const KEEPER = toArea(person(keeperId) ?? { x: GOAL_X, y: 34 });
const TARGET = toArea(shot.end ?? { x: GOAL_X, y: 34 });

/** The Ashvale outfield player nearest the keeper's line of sight to the shooter, and how far off it. */
function nearestToSightline() {
  const ab = { x: SHOOTER.x - KEEPER.x, y: SHOOTER.y - KEEPER.y };
  const length2 = ab.x ** 2 + ab.y ** 2;
  return atShot.players
    .filter((p) => p.side === "away" && p.playerId !== keeperId)
    .map((p) => {
      const at = toArea(p);
      const t = Math.min(Math.max(((at.x - KEEPER.x) * ab.x + (at.y - KEEPER.y) * ab.y) / length2, 0), 1);
      const off = Math.hypot(at.x - (KEEPER.x + t * ab.x), at.y - (KEEPER.y + t * ab.y));
      return { at, off };
    })
    .sort((a, b) => a.off - b.off)[0];
}
const blocker = nearestToSightline();
const BLOCKS_VIEW = blocker !== undefined && blocker.off < 1.5;
const FAR_POST = Math.sign(TARGET.x) !== Math.sign(SHOOTER.x);
const ORDINAL = ["", "primer", "segundo", "tercer", "cuarto", "quinto", "sexto", "séptimo"];

/** Labels sit on the side away from the shot's line, so none of them crosses it. */
const people = [
  { at: KEEPER, label: "Portero", className: shotStyles.keeper, side: 1 },
  ...(blocker ? [{ at: blocker.at, label: "Defensa", className: shotStyles.defender, side: -1 }] : []),
  { at: SHOOTER, label: shot.player, className: shotStyles.shooter, side: 1 },
];

function GoalArea() {
  return (
    <svg
      className={shotStyles.goal}
      viewBox="-22 -2.5 44 24"
      role="img"
      aria-label={`${shot.player} dispara desde ${shotDistance} metros${FAR_POST ? " al palo largo" : ""}`}
    >
      <defs>
        <marker
          id="shot-head"
          viewBox="0 0 10 10"
          refX="7"
          refY="5"
          markerWidth="4"
          markerHeight="4"
          orient="auto"
        >
          <path d="M0 1 L9 5 L0 9 Z" fill="context-stroke" />
        </marker>
      </defs>
      <path
        d="M-20.16 0V16.5H20.16V0M-9.16 0V5.5H9.16V0M-22 0H22M-7.31 16.5A9.15 9.15 0 0 0 7.31 16.5"
        className={shotStyles.chalk}
      />
      <circle cx={0} cy={11} r={0.3} className={shotStyles.spot} />
      <path d="M-3.66 0V-1.6H3.66V0" className={shotStyles.frame} />
      {BLOCKS_VIEW && blocker && (
        <line
          x1={KEEPER.x}
          y1={KEEPER.y}
          x2={blocker.at.x}
          y2={blocker.at.y}
          className={shotStyles.sightline}
        />
      )}
      <line
        x1={SHOOTER.x}
        y1={SHOOTER.y}
        x2={TARGET.x}
        y2={TARGET.y}
        className={shotStyles.path}
        markerEnd="url(#shot-head)"
      />
      {people.map(({ at, label, className, side }) => (
        <g key={label}>
          <circle cx={at.x} cy={at.y} r={1.1} className={className} />
          <text
            x={at.x + side * 1.8}
            y={at.y + 0.6}
            className={shotStyles.label}
            textAnchor={side > 0 ? "start" : "end"}
          >
            {label}
          </text>
        </g>
      ))}
    </svg>
  );
}

/**
 * The casual lens, in Spanish: the story in one picture and two sentences, and simple switches. When the
 * room sent the keeper's view to this phone, that is the story; when this fan's pick is on the TV, it is
 * the TV's story, told simply in Spanish.
 */
export function CasualView({ fan, ownPick }: { fan: CastId; ownPick?: string }) {
  const keepersView = ownPick === "keepers-view";
  return (
    <div className={styles.content}>
      <ScoreLine />
      <section className={styles.block}>
        <HelperTag fan={fan}>{keepersView ? copy.es.fromHelper : copy.es.onTvYourWay}</HelperTag>
        <h2 className={styles.headline}>
          {keepersView ? "Cómo lo vio el portero de Ashvale" : goal.copy.es_headline}
        </h2>
        <div className={shotStyles.card}>
          <GoalArea />
        </div>
        <p className={styles.lede}>
          {keepersView ? (
            <>
              {shot.player} llegó en carrera y disparó desde {shotDistance} metros
              {FAR_POST ? ", cruzado, al palo largo" : ""}.{" "}
              {BLOCKS_VIEW
                ? "Un defensa le tapaba la vista al portero."
                : `Fue el ${ORDINAL[goal.scoreAfter.home] ?? ""} gol de Kestrel.`}
            </>
          ) : (
            goal.copy.es_line
          )}
        </p>
      </section>
      <section>
        <Switch label="Subtítulos en la tele" hint="En español, debajo del inglés" defaultOn />
        <Switch label="Más detalle" hint="Números y tácticas" />
      </section>
    </div>
  );
}
