import head from "../../../illustration/pip-head.webp";
import wordmark from "../../../logo/wordmark.svg";
import wordmarkReversed from "../../../logo/wordmark-reversed.svg";

export type WordmarkVariant = "wordmark" | "lockup";

interface WordmarkProps {
  /** `lockup` puts Pip's head before the word: page headers and the join screen. */
  variant?: WordmarkVariant;
  /** White letters, for the navy field and the video. */
  reversed?: boolean;
  /** Height of the letters in pixels. The wordmark is never narrower than 96px. */
  height: number;
  className?: string;
}

/** The Front Room logo. Never beside a score, never recoloured, never set in another face. */
export function Wordmark({ variant = "wordmark", reversed = false, height, className }: WordmarkProps) {
  const word = <img src={reversed ? wordmarkReversed : wordmark} alt="Front Room" height={height} />;
  if (variant === "wordmark") {
    return <span className={className}>{word}</span>;
  }
  return (
    <span className={className} style={{ display: "inline-flex", alignItems: "center", gap: height * 0.35 }}>
      <img src={head} alt="" height={height * 1.7} style={{ width: "auto" }} />
      {word}
    </span>
  );
}
