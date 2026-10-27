import room from "@frontroom/design/illustration/room-hero.jpg";
import { fanById } from "../../fixtures/room";
import { Scaled } from "../../ui/Scaled";
import { FanPhone } from "../phone/PhoneSurface";
import { TvSurface } from "../tv/TvSurface";
import styles from "./HeroRoom.module.css";

/**
 * The family on the sofa, drawn, with the real product on their screens: the phones in the drawing are
 * captures (imagery/compose_room.py) and the TV is the live TV surface, replaying the goal with the room's
 * pick. Either side, two of their phones running for real, so the private side reads as well as the TV.
 * The TV's box is where illustration/source/widen_tv.py put the screen, as fractions of the picture.
 */
const SCREEN = { left: 32.12, top: 2.23, width: 35.77, height: 35.81 };

function SidePhone({ id, label }: { id: string; label: string }) {
  return (
    <figure className={styles.side}>
      <Scaled width={414} height={868} className={styles.phone}>
        <FanPhone fan={fanById(id)} />
      </Scaled>
      <figcaption>{label}</figcaption>
    </figure>
  );
}

export function HeroRoom() {
  return (
    <div className={styles.stage}>
      <SidePhone id="rob" label="Rob's phone: the numbers" />
      <figure className={styles.room}>
        <img
          src={room}
          alt="A family on the sofa watching football. The TV shows what the room agreed on, and each of their four phones shows something different."
          className={styles.picture}
        />
        <div
          className={styles.tv}
          style={{
            left: `${SCREEN.left}%`,
            top: `${SCREEN.top}%`,
            width: `${SCREEN.width}%`,
            height: `${SCREEN.height}%`,
          }}
          aria-hidden="true"
        >
          <Scaled width={1920} height={1080}>
            <TvSurface state="origin" loopReplay overlayThroughout />
          </Scaled>
        </div>
        <figcaption className={styles.call}>
          <strong>Pip's call</strong>
          “Where it started” goes on the TV: fair to both clubs. The pressing map goes to Rob's and Sam's
          phones.
        </figcaption>
      </figure>
      <SidePhone id="ana" label="Ana's phone: in Spanish" />
    </div>
  );
}
