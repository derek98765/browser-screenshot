#!/usr/bin/env python3
"""
Crop one region out of a screenshot, in CSS pixels.

Why this exists
---------------
Partial screenshots need just one element or section. The Claude for Chrome
extension captures the whole viewport, so we take that shot and crop it to
the element's getBoundingClientRect().

Screenshots come back at DEVICE pixels, which differ from CSS pixels whenever
page zoom or a HiDPI scale factor is in play. We infer the scale from
(image width / viewport width) rather than assuming 1:1, so the crop lands on
the right pixels, then resample to exact CSS size.

Usage
-----
  crop.py IN.png OUT.png X Y W H --viewport-width VW [--pad P] [--native]

  X Y W H          CSS-pixel rect of the region inside IN.png (for a single
                   viewport shot this is getBoundingClientRect(); for a stitched
                   full-page image it is the rect plus scrollY)
  --viewport-width CSS width IN.png represents (innerWidth for a viewport shot,
                   the layout width for a stitched image)
  --pad P          extra CSS px of breathing room on every side (default 0),
                   clamped to the image edges
  --native         keep device-pixel resolution instead of resampling to CSS
                   size (sharper on HiDPI; dimensions are then W*scale)

Examples
--------
  crop.py shot.png pricing-card.png 480 212 360 540 --viewport-width 1920 --pad 16
  crop.py page-desktop.png footer.png 0 4210 1920 380 --viewport-width 1920
"""

import sys
import os

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required:  pip3 install pillow")


def take_opt(args, name, cast, default):
    if name not in args:
        return default
    i = args.index(name)
    try:
        value = cast(args[i + 1])
    except (IndexError, ValueError):
        sys.exit(f"{name} needs a number")
    del args[i : i + 2]
    return value


def main(argv):
    args = list(argv[1:])

    native = "--native" in args
    if native:
        args.remove("--native")
    viewport_w = take_opt(args, "--viewport-width", float, None)
    pad = take_opt(args, "--pad", float, 0.0)

    if len(args) != 6 or viewport_w is None:
        sys.exit(__doc__.strip())

    in_path, out_path = args[0], args[1]
    x, y, w, h = (float(v) for v in args[2:6])

    img = Image.open(in_path).convert("RGB")
    scale = img.width / viewport_w

    left = max(0, round((x - pad) * scale))
    top = max(0, round((y - pad) * scale))
    right = min(img.width, round((x + w + pad) * scale))
    bottom = min(img.height, round((y + h + pad) * scale))
    if right <= left or bottom <= top:
        sys.exit(
            f"Region is outside the image ({img.width}x{img.height} device px, "
            f"scale {scale:.3f}). Check the rect and --viewport-width."
        )

    region = img.crop((left, top, right, bottom))
    if not native:
        css_size = (max(1, round(region.width / scale)), max(1, round(region.height / scale)))
        region = region.resize(css_size, Image.LANCZOS)
    region.save(out_path, "PNG", optimize=True)

    notes = []
    if abs(scale - 1.0) >= 0.01:
        notes.append(f"source at {scale:.3f}×" + (", kept native" if native else ""))
    if x < 0 or y < 0 or (x + w) * scale > img.width + 1 or (y + h) * scale > img.height + 1:
        notes.append("rect extends past the image — region is clipped")
    suffix = f"  [{', '.join(notes)}]" if notes else ""
    print(f"{out_path}  {region.width}x{region.height}{suffix}")


if __name__ == "__main__":
    main(sys.argv)
