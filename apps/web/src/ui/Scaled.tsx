import { type ReactNode, useLayoutEffect, useRef, useState } from "react";

interface ScaledProps {
  /** The size the child is laid out at: a 1920×1080 TV, a 414×868 phone. */
  width: number;
  height: number;
  /** Never grow past this scale. */
  max?: number;
  className?: string;
  children: ReactNode;
}

/** Shows a fixed-size screen (the real TV or phone, not a picture of it) scaled to fit the width it is given. */
export function Scaled({ width, height, max = 1, className, children }: ScaledProps) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);

  useLayoutEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const resize = () => setScale(Math.min(max, frame.clientWidth / width));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(frame);
    return () => observer.disconnect();
  }, [width, max]);

  return (
    <div ref={frameRef} className={className} style={{ height: height * scale, overflow: "hidden" }}>
      <div style={{ width, height, transform: `scale(${scale})`, transformOrigin: "top left" }}>
        {children}
      </div>
    </div>
  );
}
