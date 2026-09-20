"""What changed between two `visual_snapshot.py --styles` runs.

    python tools/style_compare.py <before-folder> <after-folder> [--detail N]

For each view, counts elements whose computed style or box changed, then lists
the most common changes (property: before -> after). Exit status 1 when
anything differs, so a refactor step that should change nothing can be
checked by the exit code alone.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path


def load(path: Path) -> dict:
    # Each run serves the page on a new port; a URL is the same asset whatever
    # port it came from.
    text = re.sub(r"https?://127\.0\.0\.1:\d+", "http://local", path.read_text(encoding="utf-8"))
    return json.loads(text)


def main() -> int:
    args = sys.argv[1:]
    detail = 12
    if "--detail" in args:
        index = args.index("--detail")
        detail = int(args[index + 1])
        del args[index:index + 2]
    before, after = Path(args[0]), Path(args[1])
    views = sorted(before.glob("*.styles.json"))
    if not views:
        print(f"no style snapshots in {before}")
        return 2
    changed_any = False
    for old in views:
        new = after / old.name
        view = old.name.removesuffix(".styles.json")
        if not new.is_file():
            print(f"{view}: missing after")
            changed_any = True
            continue
        a, b = load(old), load(new)
        gone, added = set(a) - set(b), set(b) - set(a)
        changes = collections.Counter()
        examples = {}
        moved = 0
        for key in set(a) & set(b):
            for name, value in a[key].items():
                other = b[key].get(name)
                if other == value:
                    continue
                if name == "box":
                    moved += 1
                    continue
                label = f"{name}: {value} -> {other}"
                changes[label] += 1
                examples.setdefault(label, key)
        if not (gone or added or changes or moved):
            continue
        changed_any = True
        print(f"{view}: {len(changes)} style changes, {moved} moved/resized, "
              f"{len(gone)} elements gone, {len(added)} new")
        for label, count in changes.most_common(detail):
            print(f"  {count:4} x {label[:140]}")
            print(f"         e.g. {examples[label][-120:]}")
    if not changed_any:
        print("no differences")
    return 1 if changed_any else 0


if __name__ == "__main__":
    sys.exit(main())
