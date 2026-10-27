"""Make the drawn room's TV screen exactly 16:9, so a real 1920x1080 capture fits without cropping.

    uv run --no-project --with pillow python widen_tv.py

The generator drew the screen at about 2.1:1. Above the TV there is only plain wall, so the screen grows
upwards: the bezel and the chroma-green screen are repainted taller, keeping the bottom edge where it
was. Writes room-16x9.png, the source for imagery/compose_room.py.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent

# Measured on room.png: the green screen spans x 537-1134 and y 72-357; the bezel is about 10px wide.
SCREEN_LEFT, SCREEN_RIGHT, SCREEN_BOTTOM = 537, 1134, 357
BEZEL = 10
BEZEL_COLOUR = (38, 41, 39)
GREEN = (0, 255, 0)


def main() -> None:
    room = Image.open(HERE / "room.png").convert("RGB")
    width = SCREEN_RIGHT - SCREEN_LEFT
    top = SCREEN_BOTTOM - round(width * 9 / 16)
    draw = ImageDraw.Draw(room)
    draw.rounded_rectangle(
        (SCREEN_LEFT - BEZEL, top - BEZEL, SCREEN_RIGHT + BEZEL, SCREEN_BOTTOM + BEZEL),
        radius=6,
        fill=BEZEL_COLOUR,
    )
    draw.rectangle((SCREEN_LEFT, top, SCREEN_RIGHT, SCREEN_BOTTOM), fill=GREEN)
    room.save(HERE / "room-16x9.png")
    # Where the screen sits, as fractions of the picture, for pages that lay the live TV over it.
    w, h = room.size
    print(
        f"screen: left {SCREEN_LEFT / w:.4f}, top {top / h:.4f}, "
        f"width {(width + 1) / w:.4f}, height {(SCREEN_BOTTOM - top + 1) / h:.4f}"
    )


if __name__ == "__main__":
    main()
