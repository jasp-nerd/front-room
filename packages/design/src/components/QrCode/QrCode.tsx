import QRCode from "qrcode";
import { useMemo } from "react";

/** A scannable QR code drawn as one SVG path: dark modules on a light quiet zone, which every phone can read. */
export function QrCode({ text, size, label }: { text: string; size: number; label: string }) {
  const { path, count } = useMemo(() => {
    const { modules } = QRCode.create(text, { errorCorrectionLevel: "M" });
    let d = "";
    for (let row = 0; row < modules.size; row += 1) {
      for (let col = 0; col < modules.size; col += 1) {
        if (modules.get(row, col)) d += `M${col} ${row}h1v1h-1z`;
      }
    }
    return { path: d, count: modules.size };
  }, [text]);

  const quiet = 4;
  return (
    <svg
      width={size}
      height={size}
      viewBox={`${-quiet} ${-quiet} ${count + 2 * quiet} ${count + 2 * quiet}`}
      role="img"
      aria-label={label}
      shapeRendering="crispEdges"
    >
      <rect x={-quiet} y={-quiet} width={count + 2 * quiet} height={count + 2 * quiet} fill="#f1f0ea" />
      <path d={path} fill="#0c1116" />
    </svg>
  );
}
