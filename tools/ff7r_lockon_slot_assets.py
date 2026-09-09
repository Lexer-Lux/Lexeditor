#!/usr/bin/env python3
"""Run the FF7R #429 marker-slot -> cooked-widget correlation on an install.

This command is read-only. It scans existing cooked/native evidence through the
main Better Lock-on probe, joins decoded BattleLockonMarkerXXWidget SoftClass
package paths to ranked cooked assets by exact normalized package path, and
reports whether the fail-closed red-reticle write gate can produce three exact
LinearColor rewrites. It never performs those writes itself.
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
from games.ff7r.lockon_slot_asset_probe import (  # noqa: E402
    correlate_marker_slots_to_assets,
    plan_red_reticle_rewrites,
)


def build_report(game_root: str | Path) -> dict:
    source = probe_better_lockon_sources(Path(game_root).expanduser().resolve())
    correlation = correlate_marker_slots_to_assets(
        source.get("serializedMarkerSlotResearch", {}),
        source.get("candidates", ()),
    )
    red_plan = plan_red_reticle_rewrites(correlation)
    return {
        "implementationReady": bool(red_plan.get("implementationReady", False)),
        "gameRoot": str(Path(game_root).expanduser().resolve()),
        "markerSlotResearch": source.get("serializedMarkerSlotResearch", {}),
        "slotAssetCorrelation": correlation,
        "redReticleWritePlan": red_plan,
        "sourceBlockers": source.get("blockers", []),
        "scanErrors": source.get("scanErrors", []),
        "notes": [
            "The command performs no writes to the game installation.",
            "A red-reticle write plan is emitted only when all three numbered dedicated lock-on marker widgets resolve uniquely and each has exactly one blue-dominant serialized LinearColor owner.",
            "All three numbered marker widgets are targeted together, so Default/Wimp/Libra slot ordering is not guessed or required for the color change.",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only FF7R #429 validation: correlate numbered lock-on marker "
            "SoftClass paths with cooked widget candidates and report the exact "
            "red-reticle write plan when the installed evidence is sufficient."
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
