import { type ReactNode, useLayoutEffect, useRef, useState } from "react";
import styles from "./FitStage.module.css";

interface FitStageProps {
  /** The size the picture is laid out at, e.g. a 1920×1080 TV or the four-phone board. */
  width: number;
  height: number;
  /** A bar above the picture, for visitors: what this page is and the way back. */
  header?: ReactNode;
  children: ReactNode;
}

/**
 * A fixed-size picture (the TV, the phone board) scaled to fit the window, centred, with nothing to scroll.
 * `?shot=1` drops the header, so captures at the picture's own size come out exactly as before.
 */
export function FitStage({ width, height, header, children }: FitStageProps) {
  const areaRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);
  const shot = new URLSearchParams(window.location.search).get("shot") === "1";

  useLayoutEffect(() => {
    const area = areaRef.current;
    if (!area) return;
    const resize = () => setScale(Math.min(area.clientWidth / width, area.clientHeight / height));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(area);
    return () => observer.disconnect();
  }, [width, height]);

  return (
    <div className={styles.page}>
      {header && !shot && <header className={styles.header}>{header}</header>}
      <div ref={areaRef} className={styles.area}>
        <div style={{ width: width * scale, height: height * scale }}>
          <div style={{ width, height, transform: `scale(${scale})`, transformOrigin: "top left" }}>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
