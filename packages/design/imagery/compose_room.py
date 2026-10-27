"""Put real captures of our surfaces onto the green screens in a picture of the room.

The source picture has five chroma-green screens: the TV and four phones. This finds each one, warps a
capture onto it with a perspective transform and, for a photo, pulls the green glow out of the hands and
faces around it. The drawn room (illustration/source/room-16x9.png) has no glow to pull, and green
plants that must keep their colour, so it skips that step.

    uv run --with pillow --with numpy --with scipy python compose_room.py \\
        --source ../illustration/source/room-16x9.png --drawn \\
        --tv tv.png --phones rob.png ana.png leo.png sam.png --out ../illustration/room-hero.jpg

Phones are listed left to right as they sit on the sofa (in the drawn room: Rob, Ana, Leo, Sam).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).parent
SOURCE = HERE.parent / "illustration" / "source" / "room-16x9.png"


def green_mask(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    return (g > 120) & (g > r + 50) & (g > b + 50)


def screens(rgb: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Every green screen, largest first: its corners (tl, tr, br, bl) and the pixels that show green."""
    labels, count = ndimage.label(green_mask(rgb))
    found = []
    for index in range(1, count + 1):
        ys, xs = np.nonzero(labels == index)
        if len(xs) < 2_000:
            continue
        s, d = xs + ys, xs - ys
        corners = np.array(
            [
                (xs[s.argmin()], ys[s.argmin()]),
                (xs[d.argmax()], ys[d.argmax()]),
                (xs[s.argmax()], ys[s.argmax()]),
                (xs[d.argmin()], ys[d.argmin()]),
            ],
            dtype=float,
        )
        found.append((len(xs), index, square_up(corners)))
    return [(corners, labels == index) for _, index, corners in sorted(found, key=lambda f: -f[0])]


def square_up(corners: np.ndarray, tolerance: float = 6.0) -> np.ndarray:
    """A screen is a parallelogram on the photo. If something in front of it (a head, a hand) hides a corner,
    that corner was found in the wrong place: rebuild it from the other three. Something in front can only
    make a screen look smaller, so of the possible repairs we keep the one with the largest area."""
    predicted = np.array([corners[i - 1] + corners[(i + 1) % 4] - corners[(i + 2) % 4] for i in range(4)])
    errors = np.linalg.norm(predicted - corners, axis=1)
    if errors.max() <= tolerance:
        return corners
    repairs = []
    for i in np.nonzero(errors > tolerance)[0]:
        repaired = corners.copy()
        repaired[i] = predicted[i]
        repairs.append((area(repaired), repaired))
    return max(repairs, key=lambda r: r[0])[1]


def area(corners: np.ndarray) -> float:
    x, y = corners[:, 0], corners[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def grow(corners: np.ndarray, pixels: float) -> np.ndarray:
    """Push each corner away from the centre so the capture covers the screen's soft green edge."""
    centre = corners.mean(axis=0)
    out = corners - centre
    return centre + out * (1 + pixels / np.linalg.norm(out, axis=1, keepdims=True))


def perspective(src_size: tuple[int, int], dst: np.ndarray) -> list[float]:
    """PIL's eight perspective coefficients mapping output pixels in `dst` back to the source image."""
    w, h = src_size
    src = np.array([(0, 0), (w, 0), (w, h), (0, h)], dtype=float)
    rows = []
    for (x, y), (u, v) in zip(dst, src, strict=True):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return list(np.linalg.solve(np.array(rows), src.reshape(8)))


def despill(rgb: np.ndarray, near: np.ndarray) -> np.ndarray:
    """Where green light spilled, cap green at the brighter of red and blue."""
    out = rgb.astype(float)
    cap = np.maximum(out[..., 0], out[..., 2]) * 1.06
    out[..., 1] = np.where(near, np.minimum(out[..., 1], cap), out[..., 1])
    return out.clip(0, 255).astype(np.uint8)


BEZEL = (30, 33, 36)


def bezel_leftover_green(base: Image.Image, screen_pixels: np.ndarray, covered: np.ndarray) -> Image.Image:
    """A drawn screen's corners are soft, so a sliver of green can survive the warp. Next to a screen it can
    only be screen edge: paint it the bezel's colour, including the half-green pixels along it. Only next to
    the five screens (the sofa, the rug and Leo's jumper are green too) and only where no capture landed (the
    captured pitch is green too)."""
    rgb = np.asarray(base).copy()
    near_screens = ndimage.binary_dilation(screen_pixels, iterations=4) & ~covered
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    greenish = (g > 90) & (g > r + 30) & (g > b + 30) & near_screens
    rgb[greenish] = BEZEL
    return Image.fromarray(rgb)


def compose(source: Path, tv: Path, phones: list[Path], out: Path, drawn: bool) -> None:
    picture = Image.open(source).convert("RGB")
    rgb = np.asarray(picture)
    found = screens(rgb)
    tv_screen, phone_screens = found[0], sorted(found[1:5], key=lambda f: f[0][:, 0].mean())

    if drawn:
        base = picture.copy()
    else:
        near = ndimage.binary_dilation(green_mask(rgb), iterations=40)
        base = Image.fromarray(despill(rgb, near))
    covered = np.zeros(rgb.shape[:2], dtype=bool)
    for capture, (corners, shows_green) in [(tv, tv_screen), *zip(phones, phone_screens, strict=True)]:
        image = Image.open(capture).convert("RGBA")
        quad = grow(corners, 2.5)
        warped = image.transform(
            base.size, Image.Transform.PERSPECTIVE, perspective(image.size, quad), Image.Resampling.BICUBIC
        )
        # Only where the screen showed green, so heads and hands in front of it stay in front.
        visible = ndimage.binary_dilation(shows_green, iterations=3)
        alpha = (np.asarray(warped)[..., 3] * visible).astype(np.uint8)
        base.paste(warped, (0, 0), Image.fromarray(alpha))
        covered |= alpha == 255
    if drawn:
        screen_pixels = np.logical_or.reduce([shows for _, shows in [tv_screen, *phone_screens]])
        base = bezel_leftover_green(base, screen_pixels, covered)
    base.save(out, quality=90)
    print(f"wrote {out}: TV and {len(phones)} phones")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--drawn", action="store_true", help="a drawing: keep greens, no spill to remove")
    parser.add_argument("--tv", type=Path, required=True)
    parser.add_argument("--phones", type=Path, nargs=4, required=True)
    parser.add_argument("--out", type=Path, default=HERE.parent / "illustration" / "room-hero.jpg")
    args = parser.parse_args()
    compose(args.source, args.tv, args.phones, args.out, args.drawn)
