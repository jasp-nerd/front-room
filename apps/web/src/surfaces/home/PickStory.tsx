import { type CastId, FanFace } from "@frontroom/design";
import spotPhone from "@frontroom/design/illustration/spot-phone.webp";
import spotTv from "@frontroom/design/illustration/spot-tv.webp";
import { type ClubId, candidates, clubs, decision, fanById, fans } from "../../fixtures/room";

/** Fans in sofa order, so every list of names reads the same way. */
const seated = (ids: string[]) => fans.map((f) => f.id).filter((id) => ids.includes(id));

import styles from "./PickStory.module.css";

const names = (ids: string[]) => {
  const list = ids.map((id) => fanById(id).name);
  return list.length > 1 ? `${list.slice(0, -1).join(", ")} and ${list.at(-1)}` : (list[0] ?? "");
};

const possessive = (ids: string[]) => {
  const list = ids.map((id) => `${fanById(id).name}'s`);
  return list.length > 1 ? `${list.slice(0, -1).join(", ")} and ${list.at(-1)}` : (list[0] ?? "");
};

/** Why Pip sent a pick where it went, in the words you'd use on the sofa. */
function reason(candidateId: string, won: boolean): string {
  if (won) return "Fair to both clubs, so the whole room sees it.";
  const favours = candidates[candidateId]?.favours;
  if (!favours) return "Another pick suited the room better.";
  const others = fans.filter((f) => f.club !== favours);
  const club = (id: ClubId) => clubs[id].name.split(" ")[0];
  return `It only shows ${club(favours)}'s side, and ${names(others.map((f) => f.id))} ${others.length > 1 ? "support" : "supports"} ${club(others[0]?.club ?? favours)}.`;
}

/** The room's real decision on Okafor's goal: the picks that lost first, the one on the TV last. */
const picks = [...decision.candidates]
  .sort((a, b) => Number(a.won) - Number(b.won))
  .map((c) => ({
    id: c.candidateId,
    title: candidates[c.candidateId]?.title ?? c.candidateId,
    askedBy: seated(c.askedBy ?? []),
    won: c.won,
    to: decision.deliveredPrivately
      .filter((d) => d.candidateId === c.candidateId)
      .map((d) => d.agentId)
      .filter((id, i, all) => all.indexOf(id) === i),
  }));

const count = ["no", "one", "two", "three", "four", "five", "six"];

/** Each pick the helpers asked for, who wanted it, and where Pip sent it: the TV, or the fans' own phones. */
export function PickStory() {
  return (
    <div className={styles.story}>
      <p className={styles.title}>
        When Okafor scored, the helpers asked for {count[picks.length] ?? picks.length} things
      </p>
      <ol className={styles.picks}>
        {picks.map((pick) => (
          <li key={pick.id} className={styles.pick} data-won={pick.won || undefined}>
            <div className={styles.what}>
              <strong className={styles.name}>{pick.title}</strong>
              <span className={styles.wanted}>
                <span className={styles.faces}>
                  {pick.askedBy.map((id) => (
                    <FanFace key={id} id={id as CastId} size={32} />
                  ))}
                </span>
                Wanted by {names(pick.askedBy)}
              </span>
              <span className={styles.why}>{reason(pick.id, pick.won)}</span>
            </div>
            <span className={styles.arrow} aria-hidden="true" />
            <div className={styles.where}>
              <img src={pick.won ? spotTv : spotPhone} alt="" className={styles.spot} />
              <strong>
                {pick.won
                  ? "On the TV"
                  : `To ${possessive(pick.to)} ${pick.to.length > 1 ? "phones" : "phone"}`}
              </strong>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
