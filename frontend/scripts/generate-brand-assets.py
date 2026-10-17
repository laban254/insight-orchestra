#!/usr/bin/env python3
"""
Generate the raster brand assets for the "IO" monogram.

    python3 frontend/scripts/generate-brand-assets.py --out frontend/app --what apple,favicon
    python3 frontend/scripts/generate-brand-assets.py --out ../marketing-insight-orchestra/app --what favicon

Draws the mark (a bar "I" beside a ring "O") in the brand ink on a
cyan→violet→fuchsia rounded tile, matching components/ui/Logo.tsx and
app/icon.svg. Pillow-only; deterministic, so the icons are reproducible rather
than unexplained binaries.
"""

import argparse
import os

from PIL import Image, ImageDraw

CYAN = (0x00, 0xDF, 0xFD)
VIOLET = (0xB0, 0x85, 0xFF)
FUCHSIA = (0xFF, 0x54, 0xF9)
INK = (0x03, 0x0B, 0x1C)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def stop(t):
    """Brand gradient: cyan → violet (55%) → fuchsia, along 135°."""
    t = max(0.0, min(1.0, t))
    if t <= 0.55:
        return lerp(CYAN, VIOLET, t / 0.55)
    return lerp(VIOLET, FUCHSIA, (t - 0.55) / 0.45)


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    px = img.load()
    denom = 2 * size - 2
    for y in range(size):
        for x in range(size):
            px[x, y] = (*stop((x + y) / denom), 255)

    # Rounded-square mask.
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=round(size * 0.22), fill=255)
    img.putalpha(mask)

    # Glyph, scaled from the 24-unit grid used in Logo.tsx / icon.svg.
    s = size / 24
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        [2.9 * s, 4.5 * s, (2.9 + 3.2) * s, (4.5 + 15) * s], radius=round(1.6 * s), fill=INK
    )
    ro = 5.2 + 3.2 / 2  # ring outer radius
    d.ellipse(
        [(14.3 - ro) * s, (12 - ro) * s, (14.3 + ro) * s, (12 + ro) * s],
        outline=INK,
        width=round(3.2 * s),
    )
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output directory (e.g. frontend/app)")
    ap.add_argument("--what", default="apple,favicon", help="comma list: apple,favicon")
    args = ap.parse_args()
    want = {w.strip() for w in args.what.split(",")}
    os.makedirs(args.out, exist_ok=True)

    if "apple" in want:
        p = os.path.join(args.out, "apple-icon.png")
        render(180).save(p)
        print("wrote", p, f"({os.path.getsize(p)} bytes)")
    if "favicon" in want:
        p = os.path.join(args.out, "favicon.ico")
        render(64).save(p, sizes=[(16, 16), (32, 32), (48, 48)])
        print("wrote", p, f"({os.path.getsize(p)} bytes)")


if __name__ == "__main__":
    main()
