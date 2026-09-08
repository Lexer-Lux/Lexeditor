#!/usr/bin/env python3
"""Compare controlled FF7R before/after saves for Assessed-state research.

Examples:
  python tools/ff7r_assess_save_diff.py \
    --pair run1 before1.sav after1.sav \
    --pair run2 before2.sav after2.sav

  python tools/ff7r_assess_save_diff.py \
    --pair assess1 before-a1.sav after-a1.sav \
    --pair assess2 before-a2.sav after-a2.sav \
    --control noop1 before-c1.sav after-c1.sav \
    --control noop2 before-c2.sav after-c2.sav

  python tools/ff7r_assess_save_diff.py \
    --group GuardDog before-dog-1.sav after-dog-1.sav \
    --group GuardDog before-dog-2.sav after-dog-2.sav \
    --group SecurityOfficer before-officer-1.sav after-officer-1.sav \
    --group SecurityOfficer before-officer-2.sav after-officer-2.sav \
    --control noop1 before-c1.sav after-c1.sav \
    --control noop2 before-c2.sav after-c2.sav

The tool is read-only and format-agnostic. It never modifies a save file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

# Running this file directly puts tools/ rather than the repository root on
# sys.path. Add only the parent directory so the normal games.ff7r package is
# imported exactly as it is in Lexeditor/tests.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from games.ff7r.save_control_probe import (  # noqa: E402
    analyze_controlled_experiment_groups,
    analyze_controlled_save_pairs,
)
from games.ff7r.save_diff_probe import (  # noqa: E402
    SavePair,
    analyze_experiment_groups,
    analyze_save_pairs,
)


def _read_pair(label: str, before: str | Path, after: str | Path) -> SavePair:
    before_path = Path(before).expanduser().resolve()
    after_path = Path(after).expanduser().resolve()
    return SavePair(before_path.read_bytes(), after_path.read_bytes(), label)


def build_report(
    *,
    pair_specs: Sequence[Sequence[str]] = (),
    group_specs: Sequence[Sequence[str]] = (),
    control_specs: Sequence[Sequence[str]] = (),
) -> dict:
    if pair_specs and group_specs:
        raise ValueError("use either --pair or --group experiments, not both")
    if control_specs and not (pair_specs or group_specs):
        raise ValueError("--control requires --pair or --group Assess experiments")
    if pair_specs:
        pairs = [
            _read_pair(str(label), before, after)
            for label, before, after in pair_specs
        ]
        if control_specs:
            controls = [
                _read_pair(str(label), before, after)
                for label, before, after in control_specs
            ]
            return {
                "mode": "repeated-single-experiment-with-noop-control",
                "analysis": analyze_controlled_save_pairs(pairs, controls),
            }
        return {
            "mode": "repeated-single-experiment",
            "analysis": analyze_save_pairs(pairs),
        }
    if group_specs:
        groups: dict[str, list[SavePair]] = {}
        for name, before, after in group_specs:
            groups.setdefault(str(name), []).append(
                _read_pair(str(name), before, after)
            )
        if control_specs:
            controls = [
                _read_pair(str(label), before, after)
                for label, before, after in control_specs
            ]
            return {
                "mode": "cross-enemy-experiments-with-noop-control",
                "analysis": analyze_controlled_experiment_groups(groups, controls),
            }
        return {
            "mode": "cross-enemy-experiments",
            "analysis": analyze_experiment_groups(groups),
        }
    raise ValueError("at least one --pair or --group experiment is required")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only FF7R save differential research for locating the per-save "
            "Assessed-enemy state used by issue #424."
        )
    )
    experiments = parser.add_argument_group("experiments")
    experiments.add_argument(
        "--pair", action="append", nargs=3, metavar=("LABEL", "BEFORE", "AFTER"),
        default=[], help="repeat one controlled enemy Assess experiment",
    )
    experiments.add_argument(
        "--control", action="append", nargs=3, metavar=("LABEL", "BEFORE", "AFTER"),
        default=[], help="repeat a no-op save from the same duplicated pre-Assessment baseline",
    )
    experiments.add_argument(
        "--group", action="append", nargs=3, metavar=("ENEMY", "BEFORE", "AFTER"),
        default=[], help="repeat for multiple named enemies to compare stable changes",
    )
    parser.add_argument(
        "--output", type=Path,
        help="optional JSON output path; stdout is used when omitted",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = build_report(
            pair_specs=args.pair,
            group_specs=args.group,
            control_specs=args.control,
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
