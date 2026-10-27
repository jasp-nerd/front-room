"""Cut the generated sheets into one transparent image per figure.

    uv run --with pillow --with numpy --with scipy python packages/design/illustration/source/cutout.py

Each sheet was generated on flat white (the prompts are next to the PNGs). The white that touches the
sheet's edge becomes transparent, with a soft edge so the drawings keep their anti-aliasing. Each
figure is then a connected group of opaque pixels, named in reading order (top row first, left to
right). The faint ground shadows the generator draws are kept: they belong to the figure.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).parent
OUT = HERE.parent

# Sheet -> (figure names in reading order, whether to drop the generator's grey ground shadows).
# Shadows (a warm grey, about #ede5dc) are dropped only for the robins: on a colour field they read as
# a white plate, and nothing else on a robin is that pale and open to the background (the cream belly
# is more yellow). Sam's white hair would be.
SHEETS = {
    "pip-poses.png": (["pip-neutral", "pip-wave", "pip-whistle", "pip-remote",
                       "pip-cheer", "pip-think", "pip-phone", "pip-sleep"], True),
    "helpers.png": (["helper-sun", "helper-sky", "helper-pink", "helper-pitch"], True),
    "people.png": (["fan-rob", "fan-ana", "fan-leo", "fan-sam"], False),
    # The logo mark: the plain head from mark.prompt.txt's sheet (its two sample tiles are cropped off).
    "pip-head.png": (["pip-head"], False),
    # Objects for the pages that explain the system: the investigators, the studio, the TV, a phone.
    "spots.png": (["spot-investigate", "spot-camera", "spot-tv", "spot-phone"], False),
}

# How far from pure white (0-255, per channel) still counts as background; the fade band softens edges.
HARD, SOFT = 10, 34
MAX_SIDE = 720


def alpha_from_white(rgb: np.ndarray, drop_shadows: bool) -> np.ndarray:
    channels = rgb.astype(np.int16)
    distance = (255 - channels).max(axis=2)
    near_white = distance <= SOFT
    if drop_shadows:
        grey = (channels.max(axis=2) - channels.min(axis=2) <= 24) & (channels.min(axis=2) >= 205)
        near_white |= grey
        distance = np.where(grey, 0, distance)
    # Only white connected to the border is background; white inside a figure (eyes, the whistle) stays.
    labels, _ = ndimage.label(near_white)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, border[border > 0])
    alpha = np.full(distance.shape, 255, dtype=np.uint8)
    fade = np.clip((distance - HARD) / (SOFT - HARD), 0, 1)
    alpha[background] = (fade[background] * 255).astype(np.uint8)
    return alpha


def figures(alpha: np.ndarray, count: int) -> list[tuple[np.ndarray, tuple[slice, slice]]]:
    # Close small gaps (a whistle cord, a shadow under the feet) so each figure is one blob.
    solid = ndimage.binary_closing(alpha > 24, iterations=12)
    labels, n = ndimage.label(solid)
    boxes = ndimage.find_objects(labels)
    sizes = ndimage.sum(solid, labels, range(1, n + 1))
    biggest = sorted(range(n), key=lambda i: -sizes[i])[:count]
    # Sheets of up to four figures are one row; the eight Pip poses are two. Order by row, then left to right.
    rows = 1 if count <= 4 else 2
    row_height = alpha.shape[0] / rows

    def row_then_left(i: int) -> tuple[int, int]:
        middle = (boxes[i][0].start + boxes[i][0].stop) / 2
        return int(middle // row_height), boxes[i][1].start

    biggest.sort(key=row_then_left)
    # Each figure keeps only its own pixels, so a neighbour's wing tip never shows in its crop.
    return [(labels == i + 1, boxes[i]) for i in biggest]


def cut(sheet: str, names: list[str], drop_shadows: bool) -> None:
    image = Image.open(HERE / sheet).convert("RGB")
    rgb = np.asarray(image)
    alpha = alpha_from_white(rgb, drop_shadows)
    found = figures(alpha, len(names))
    if len(found) != len(names):
        raise SystemExit(f"{sheet}: found {len(found)} figures, expected {len(names)}")
    for name, (mask, (rows, cols)) in zip(names, found, strict=True):
        rgba = np.dstack([rgb, np.where(mask, alpha, 0).astype(np.uint8)])
        pad = 8
        crop = rgba[max(rows.start - pad, 0) : rows.stop + pad, max(cols.start - pad, 0) : cols.stop + pad]
        figure = Image.fromarray(crop, "RGBA")
        figure.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        figure.save(OUT / f"{name}.webp", quality=90, method=6)
        figure.save(OUT / f"{name}.png", optimize=True)
        print(f"{name}: {figure.size[0]}x{figure.size[1]}")


if __name__ == "__main__":
    for sheet, (names, drop_shadows) in SHEETS.items():
        cut(sheet, names, drop_shadows)
