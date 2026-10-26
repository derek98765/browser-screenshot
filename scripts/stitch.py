#!/usr/bin/env python3
"""
Stitch viewport tiles into one full-page image at exact CSS pixel dimensions.

Why this exists
---------------
The Claude for Chrome extension can only screenshot the visible viewport, so a
full-page capture means shooting the page in slices and reassembling them.

Two things make that non-trivial:

1. Tiles come back at the window's DEVICE width, which is not the CSS layout
   width whenever page zoom or a HiDPI scale factor is in play. We infer the
   scale from (tile width / layout width) rather than assuming 1:1, then
   resample the finished image back to true CSS pixels — so the output is
   exactly LAYOUT_W wide regardless of how the browser was rendering.

2. The final tile's scroll offset is clamped to (docHeight - viewportHeight),
   so it overlaps the one before it. Positioning each tile by its RECORDED
   scrollY handles that automatically: the overlap just overwrites identical
   pixels.

Usage
-----
  stitch.py OUT.png CONTENT_W DOC_H tile.jpg:scrollY [...] [--viewport-width VW]

  CONTENT_W        CSS width of the content you want OUT
  DOC_H            CSS height of the scrolling document
  tile:Y           saved tile path and the ACTUAL scrollY when it was taken
  tile:X,Y         native 1:1 `zoom` tile, pasted unscaled at CSS (X, Y)
                   (X = the zoom region's left edge, Y = scrollY)
  --viewport-width CSS width of the browser viewport the tiles were shot at.
                   Defaults to CONTENT_W.

                   Set this when the content is narrower than the window —
                   i.e. the tablet/mobile iframe technique, where a 393px
                   iframe is pinned to the left of a 1920px window. The tile
                   is 1920 wide but only its leftmost 393 CSS px are content,
                   so we crop before scaling.

Examples
--------
  # desktop: content fills the window
  stitch.py home-desktop.png 1920 1565 t0.jpg:0 t1.jpg:692

  # mobile: 393px iframe inside a 1920px window
  stitch.py home-mobile.png 393 8648 t0.jpg:0 t1.jpg:852 --viewport-width 1920
"""

import sys
import os

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required:  pip3 install pillow")

# Page canvas fill, used only where no tile covers (rounding at the seams).
# A warm near-white reads as "page background" on most sites; override if the
# page is dark.
BG = os.environ.get("STITCH_BG", "#FBF9F6")


def main(argv):
    args = list(argv[1:])

    viewport_w = None
    if "--viewport-width" in args:
        i = args.index("--viewport-width")
        try:
            viewport_w = int(args[i + 1])
        except (IndexError, ValueError):
            sys.exit("--viewport-width needs an integer")
        del args[i : i + 2]

    if len(args) < 4:
        sys.exit(__doc__.strip())

    out_path = args[0]
    content_w = int(args[1])
    doc_h = int(args[2])
    if viewport_w is None:
        viewport_w = content_w

    specs = []
    for arg in args[3:]:
        path, _, pos = arg.rpartition(":")
        if not path:
            sys.exit(f"Malformed tile spec {arg!r} — expected path:scrollY or path:x,y")
        if "," in pos:
            x, y = pos.split(",")
            specs.append((path, int(float(x)), int(float(y))))
        else:
            specs.append((path, None, int(pos)))

    # path:x,y tiles are native 1:1 `zoom` captures: paste them at CSS (x, y)
    # with no scaling, so the output keeps full resolution.
    if any(s[1] is not None for s in specs):
        canvas = Image.new("RGB", (content_w, doc_h), BG)
        for path, x, y in specs:
            tile = Image.open(path).convert("RGB")
            canvas.paste(tile, (x or 0, y))
        canvas.save(out_path, "PNG", optimize=True)
        print(f"{out_path}  {content_w}x{doc_h}  ({len(specs)} native tiles)")
        return

    specs = [(p, y) for p, _, y in specs]
    specs.sort(key=lambda s: s[1])

    first = Image.open(specs[0][0])
    native_w = first.width
    # Tiles are captured at the WINDOW's device width, so the scale that maps
    # CSS px → captured px comes from the viewport, not from the content.
    scale = native_w / viewport_w

    crop_w = min(native_w, max(1, round(content_w * scale)))
    canvas_h = max(1, round(doc_h * scale))
    canvas = Image.new("RGB", (crop_w, canvas_h), BG)

    for path, scroll_y in specs:
        tile = Image.open(path).convert("RGB")
        if tile.width != native_w:
            sys.exit(
                f"Tile width mismatch: {os.path.basename(path)} is {tile.width}px, "
                f"expected {native_w}px. All tiles must come from one capture run "
                f"at one window size."
            )
        if crop_w < tile.width:
            tile = tile.crop((0, 0, crop_w, tile.height))
        canvas.paste(tile, (0, round(scroll_y * scale)))

    final = canvas.resize((content_w, doc_h), Image.LANCZOS)
    final.save(out_path, "PNG", optimize=True)

    notes = []
    if abs(scale - 1.0) >= 0.01:
        notes.append(f"rendered at {scale:.3f}×")
    if crop_w < native_w:
        notes.append(f"cropped {native_w}→{crop_w}px")
    suffix = f"  [{', '.join(notes)}]" if notes else ""
    print(f"{out_path}  {final.width}x{final.height}  ({len(specs)} tiles){suffix}")


if __name__ == "__main__":
    main(sys.argv)
