"""Build the Front Room wordmark: "Front Room" in Gabarito ExtraBold, as outlines.

The mark (Pip's head, `logo/mark*.png`) carries the character; the wordmark stays plain so it reads at
any size and in one colour.

    uv run --no-project --with fonttools --with brotli python build_wordmark.py

Writes logo/wordmark.svg (ink) and logo/wordmark-reversed.svg (white, for the navy field and video).
"""

from __future__ import annotations

from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).parent
FONT = HERE.parents[1] / "fonts" / "Gabarito-Variable.woff2"
TEXT = "Front Room"
WEIGHT = 800
TRACKING = -0.02  # of the em, as the display style sets it
INK, WHITE = "#14202f", "#ffffff"


def outline(font: TTFont) -> tuple[str, tuple[float, float, float, float]]:
    """One SVG path for the whole line, in font units with y flipped, and its bounds."""
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    upem = font["head"].unitsPerEm
    path = SVGPathPen(glyphs, ntos=lambda n: f"{n:.1f}".rstrip("0").rstrip("."))
    bounds = BoundsPen(glyphs)
    x = 0.0
    for char in TEXT:
        name = cmap[ord(char)]
        # Flip y (fonts draw upwards) and advance along the line.
        for pen in (path, bounds):
            glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, x, 0)))
        x += glyphs[name].width + TRACKING * upem
    return path.getCommands(), bounds.bounds


def svg(commands: str, bounds: tuple[float, float, float, float], fill: str) -> str:
    x0, y0, x1, y1 = bounds
    width, height = x1 - x0, y1 - y0
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {width:.0f} {height:.0f}" '
        f'role="img"><title>Front Room</title><path fill="{fill}" d="{commands}"/></svg>\n'
    )


def main() -> None:
    font = instantiateVariableFont(TTFont(FONT), {"wght": WEIGHT})
    commands, bounds = outline(font)
    out = HERE.parent
    (out / "wordmark.svg").write_text(svg(commands, bounds, INK))
    (out / "wordmark-reversed.svg").write_text(svg(commands, bounds, WHITE))
    print("wrote wordmark.svg, wordmark-reversed.svg")


if __name__ == "__main__":
    main()
