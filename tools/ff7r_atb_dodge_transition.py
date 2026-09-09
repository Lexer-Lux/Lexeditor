#!/usr/bin/env python3
"""Inspect FF7R dodge-predicate -> SetATB call-sequence leads.

Read-only: scans exact common `.pdata` callers in the installed executable and
reports direct call ordering plus recognizable conditional branches. The output
never validates once-per-dodge semantics or enables ATB subtraction.
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

from games.ff7r.atb_dodge_transition_probe import (  # noqa: E402
    probe_dodge_atb_call_sequences,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only FF7R #425 research: inspect exact callers shared by dodge "
            "predicates and SetATB-family functions for ordered call/branch leads."
        )
    )
    parser.add_argument("game_root", type=Path, help="FF7 Remake Intergrade installation root")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = probe_dodge_atb_call_sequences(
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
