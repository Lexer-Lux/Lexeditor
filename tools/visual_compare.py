"""Put two visual_snapshot runs side by side, one image per screen.

    python tools/visual_compare.py <before-folder> <after-folder> <output-folder>

Each output shows BEFORE on the left and AFTER on the right, and the listing
ranks screens by how much of them changed, so the biggest changes are read
first.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


def main() -> int:
    before, after, out = (Path(arg) for arg in sys.argv[1:4])
    out.mkdir(parents=True, exist_ok=True)
    ranked = []
    for shot in sorted(after.glob("*.png")):
        old = before / shot.name
        new_image = Image.open(shot).convert("RGB")
        if not old.is_file():
            ranked.append((100.0, shot.name + " (new screen)"))
            continue
        old_image = Image.open(old).convert("RGB").resize(new_image.size)
        diff = ImageChops.difference(old_image, new_image).convert("L").point(lambda v: 255 if v > 24 else 0)
        changed = 100 * sum(diff.histogram()[255:]) / (diff.width * diff.height)
        ranked.append((changed, shot.name))
        half = (new_image.width // 2, new_image.height // 2)
        pair = Image.new("RGB", (half[0] * 2 + 8, half[1] + 22), "white")
        pair.paste(old_image.resize(half), (0, 22))
        pair.paste(new_image.resize(half), (half[0] + 8, 22))
        draw = ImageDraw.Draw(pair)
        draw.text((6, 5), f"BEFORE  {shot.stem}", fill="black")
        draw.text((half[0] + 14, 5), f"AFTER  ({changed:.1f}% changed)", fill="black")
        pair.save(out / shot.name)
    for name in sorted(p.name for p in before.glob("*.png")):
        if not (after / name).is_file():
            ranked.append((100.0, name + " (screen gone)"))
    ranked.sort(reverse=True)
    listing = "\n".join(f"{score:5.1f}%  {name}" for score, name in ranked)
    (out / "ranking.txt").write_text(listing + "\n", encoding="utf-8")
    print(listing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
