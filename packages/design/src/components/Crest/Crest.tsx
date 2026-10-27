import ashvale from "../../../crests/ashvale.svg";
import kestrel from "../../../crests/kestrel.svg";

export type ClubId = "kestrel" | "ashvale";

const crests: Record<ClubId, { src: string; name: string; ratio: number }> = {
  kestrel: { src: kestrel, name: "Kestrel FC", ratio: 100 / 110 },
  ashvale: { src: ashvale, name: "Ashvale Athletic", ratio: 1 },
};

interface CrestProps {
  club: ClubId;
  /** Height in pixels; the width follows the crest's shape. */
  size: number;
  /** Decorative by default, because a club name is usually right beside it. */
  labelled?: boolean;
  className?: string;
}

/** A fictional club's crest. Clubs are data: crests mark a fan's own club or both clubs equally, never one alone. */
export function Crest({ club, size, labelled = false, className }: CrestProps) {
  const crest = crests[club];
  return (
    <img
      src={crest.src}
      alt={labelled ? crest.name : ""}
      height={size}
      width={Math.round(size * crest.ratio)}
      className={className}
    />
  );
}
