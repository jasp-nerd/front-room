import { type CastId, FanFace, Pip, QrCode, Wordmark } from "@frontroom/design";
import ashvaleCrest from "@frontroom/design/crests/ashvale.svg";
import kestrelCrest from "@frontroom/design/crests/kestrel.svg";
import { fans } from "../../fixtures/room";
import styles from "./JoinScreen.module.css";

const ROOM_CODE = "4821";

/**
 * Before kick-off the TV is ours: it invites everyone in the room to join from their own phone.
 * This is the only time the Front Room wordmark is on the shared screen.
 */
export function JoinScreen() {
  const joinUrl = `${window.location.origin}/join?room=${ROOM_CODE}`;
  return (
    <main className={styles.screen}>
      <section className={styles.invite}>
        <header className={styles.top}>
          <Wordmark variant="lockup" height={44} />
          <p className={styles.fixture}>
            <img src={kestrelCrest} alt="" className={styles.crest} />
            Kestrel <span className={styles.versus}>v</span> Ashvale
            <img src={ashvaleCrest} alt="" className={styles.crest} />
            <span className={styles.kickoff}>20:00</span>
          </p>
        </header>
        <h1 className={styles.headline}>Scan to join the room</h1>
        <p className={styles.lede}>
          Everyone gets a helper on their own phone, and the TV stays fair to both clubs.
        </p>
        <div className={styles.joinRow}>
          <div className={styles.qr}>
            <QrCode text={joinUrl} size={280} label="QR code to join this room" />
          </div>
          <dl className={styles.code}>
            <dt>Or enter code</dt>
            <dd>{ROOM_CODE}</dd>
          </dl>
        </div>
      </section>
      <aside className={styles.field} aria-labelledby="in-the-room">
        <p className={styles.pipLine}>Pip holds the remote and makes sure everyone gets a turn.</p>
        <Pip pose="remote" size={400} className={styles.pip} />
        <h2 id="in-the-room" className={styles.listTitle}>
          On the sofa
        </h2>
        <ul className={styles.joined}>
          {fans.map((fan) => (
            <li key={fan.id}>
              <span className={styles.face}>
                {/* The demo room is the drawn cast: Rob, Ana, Leo and Sam. */}
                <FanFace id={fan.id as CastId} size={92} />
              </span>
              {fan.name}
            </li>
          ))}
          <li className={styles.waiting}>
            <span className={styles.face} aria-hidden="true">
              +
            </span>
            You?
          </li>
        </ul>
      </aside>
    </main>
  );
}
