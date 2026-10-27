"""The app icon and favicons: Pip's head on a sun-yellow tile.

    uv run --no-project --with pillow python build_icons.py

Reads illustration/pip-head.png (cut by illustration/source/cutout.py) and writes logo/icons/.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

DESIGN = Path(__file__).parents[2]
HEAD = DESIGN / "illustration" / "pip-head.png"
OUT = DESIGN / "logo" / "icons"
SUN = "#ffc43d"


def tile(size: int, radius: float, head_share: float) -> Image.Image:
    """A rounded tile with the head centred, filling `head_share` of the tile's height."""
    scale = 4  # draw large, then shrink, for smooth corners
    big = size * scale
    icon = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(icon).rounded_rectangle((0, 0, big - 1, big - 1), radius=radius * big, fill=SUN)
    head = Image.open(HEAD).convert("RGBA")
    height = int(big * head_share)
    head = head.resize((int(head.width * height / head.height), height), Image.LANCZOS)
    icon.alpha_composite(head, ((big - head.width) // 2, (big - head.height) // 2 + big // 40))
    return icon.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (1024, 512, 192, 180):
        tile(size, 0.22, 0.74).save(OUT / f"app-icon-{size}.png", optimize=True)
    # Favicons fill more of the square and round less, so the face survives at 16px.
    favicons = {size: tile(size, 0.18, 0.86) for size in (16, 32, 48)}
    for size, image in favicons.items():
        image.save(OUT / f"favicon-{size}.png", optimize=True)
    favicons[48].save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
