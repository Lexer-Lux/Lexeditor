#!/usr/bin/env python3
"""Run the FF7R #429 marker-slot -> cooked-widget correlation on an install.

This command is read-only. It scans existing cooked/native evidence through the
main Better Lock-on probe, then joins decoded BattleLockonMarkerXXWidget
SoftClass package paths to ranked cooked assets by exact normalized package path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from games.ff7r.lockon_probe import probe_better_lockon_sources  # noqa: E402
from games.ff7r.lockon_slot_asset_probe import correlate_marker_slots_to_assets  # noqa: E402


def build_report(game_root: str | Path) -> dict:
    source = probe_better_lockon_sources(Path(game_root).expanduser().resolve())
    correlation = correlate_marker_slots_to_assets(
        source.get("serializedMarkerSlotResearch", {}),
        source.get("candidates", ()),
    )
    return {
        "implementationReady": False,
        "gameRoot": str(Path(game_root).expanduser().resolve()),
        "markerSlotResearch": source.get("serializedMarkerSlotResearch", {}),
        "slotAssetCorrelation": correlation,
        "sourceBlockers": source.get("blockers", []),
        "scanErrors": source.get("scanErrors", []),
        "notes": [
            "The command performs no writes to the game installation.",
            "A unique exact package-path correlation narrows a numbered marker slot to a cooked widget asset but does not establish marker-type or active-blue-state semantics.",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only FF7R #429 research: correlate decoded numbered lock-on marker "
            "SoftClass paths with cooked widget candidates."
        )
    )
    parser.add_argument("game_root", type=Path, help="FF7 Remake Intergrade installation root")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = build_report(args.game_root)
    except (OSError, ValueError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        target = args.output.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
