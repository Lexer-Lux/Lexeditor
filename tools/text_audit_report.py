"""Text a person cannot read, from a `visual_snapshot.py` run.

    python tools/text_audit_report.py <snapshot-folder> [--all] [--kind KIND]

Each captured view has a <view>.text.json written by tools/text_audit.js.
This groups them by view and kind. Exit status 1 when anything is clipped or
too small, so a run can gate on it. --all lists every occurrence instead of
the first few per view.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    show_all = "--all" in args
    if show_all:
        args.remove("--all")
    kind_filter = None
    if "--kind" in args:
        index = args.index("--kind")
        kind_filter = args[index + 1]
        del args[index:index + 2]
    folder = Path(args[0])
    files = sorted(folder.glob("*.text.json"))
    if not files:
        print(f"no text audits in {folder}")
        return 2
    totals = collections.Counter()
    for path in files:
        issues = json.loads(path.read_text(encoding="utf-8"))
        if kind_filter:
            issues = [issue for issue in issues if issue["kind"] == kind_filter]
        if not issues:
            continue
        view = path.name.removesuffix(".text.json")
        kinds = collections.Counter(issue["kind"] for issue in issues)
        totals.update(kinds)
        print(f"{view}: " + ", ".join(f"{count} {kind}" for kind, count in kinds.most_common()))
        for issue in issues if show_all else issues[:4]:
            extra = f"{issue['size']}px" if issue["kind"] == "tiny" else f"{issue['lost']}px lost to {issue['by'][-60:]}"
            print(f"    {issue['kind']:9} {issue['text'][:40]!r:44} {extra}")
    views = len(files)
    if not totals:
        print(f"{views} views, no unreadable text")
        return 0
    print(f"{views} views: " + ", ".join(f"{count} {kind}" for kind, count in totals.most_common()))
    return 1


if __name__ == "__main__":
    sys.exit(main())
