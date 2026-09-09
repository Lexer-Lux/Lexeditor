#!/usr/bin/env python3
"""Inspect Chapter 3 bench/vending root-component coordinate-space evidence.

Read-only. The report can prove that two serialized RelativeLocation vectors use
an explicitly identical AttachParent, but never treats that local-frame distance
as world-space adjacency or authorizes removing a bench.
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

from games.ff7r.bench_coordinate_probe import (  # noqa: E402
    probe_chapter3_bench_coordinate_space,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only FF7R #427 research: resolve bench/vending RootComponent, "
            "RelativeLocation and explicit AttachParent evidence."
        )
    )
    parser.add_argument("game_root", type=Path, help="FF7 Remake Intergrade installation root")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = probe_chapter3_bench_coordinate_space(
            args.game_root.expanduser().resolve()
        )
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
