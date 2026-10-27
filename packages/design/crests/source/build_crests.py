"""Build the two fictional club crests from their generated silhouettes.

The silhouettes were generated as flat white-on-black images (prompts beside them), traced to vector paths
with potrace, and set into each club's shape here. Needs ImageMagick (`magick`) and `potrace`.

    python build_crests.py
"""

import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent
CHALK, NIGHT = "#f1f0ea", "#0c1116"


def trace(png: Path) -> tuple[str, int]:
    """The silhouette's outline as one SVG path in potrace's coordinates, plus the image size."""
    size = int(subprocess.run(["magick", "identify", "-format", "%w", str(png)], capture_output=True,
                              text=True, check=True).stdout)
    with tempfile.TemporaryDirectory() as tmp:
        pbm, svg = Path(tmp, "in.pbm"), Path(tmp, "out.svg")
        subprocess.run(["magick", str(png), "-colorspace", "gray", "-threshold", "50%", "-negate", str(pbm)],
                       check=True)
        subprocess.run(["potrace", str(pbm), "-s", "--flat", "-t", "20", "-a", "1.0", "-O", "0.4", "-o", str(svg)],
                       check=True)
        path = re.search(r'<path d="([^"]+)"', svg.read_text(), re.S)
    assert path, f"nothing traced in {png}"
    return " ".join(path.group(1).split()), size


def mark(png: Path, box: tuple[float, float, float, float], fill: str, crop: tuple[int, int, int, int]) -> str:
    """The traced silhouette, scaled so the part of the image inside `crop` fills `box` (x, y, w, h)."""
    d, size = trace(png)
    cx0, cy0, cx1, cy1 = crop
    scale = min(box[2] / (cx1 - cx0), box[3] / (cy1 - cy0))
    dx = box[0] + (box[2] - (cx1 - cx0) * scale) / 2 - cx0 * scale
    dy = box[1] + (box[3] - (cy1 - cy0) * scale) / 2 - cy0 * scale
    return (f'<g transform="translate({dx:.2f} {dy:.2f}) scale({scale:.5f})">'
            f'<path transform="translate(0 {size}) scale(0.1 -0.1)" fill="{fill}" d="{d}"/></g>')


def kestrel() -> str:
    bird = mark(HERE / "kestrel-silhouette.png", (19, 21, 62, 58), CHALK, (130, 180, 1140, 1090))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 110" role="img"><title>Kestrel FC</title>'
        '<path d="M8 6h84v50c0 26-20 40-42 50C28 96 8 82 8 56Z" fill="#c8102e"/>'
        f'<path d="M14 12h72v44c0 21-16 33-36 42C30 89 14 77 14 56Z" fill="none" stroke="{CHALK}" stroke-width="2.5"/>'
        f"{bird}</svg>\n"
    )


def ashvale() -> str:
    leaf = mark(HERE / "ash-silhouette.png", (22, 20, 56, 60), NIGHT, (140, 30, 895, 990))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img"><title>Ashvale Athletic</title>'
        f'<circle cx="50" cy="50" r="47" fill="{NIGHT}"/><circle cx="50" cy="50" r="41" fill="#6cace4"/>'
        f"{leaf}</svg>\n"
    )


if __name__ == "__main__":
    (OUT / "kestrel.svg").write_text(kestrel())
    (OUT / "ashvale.svg").write_text(ashvale())
    print("wrote kestrel.svg and ashvale.svg")
