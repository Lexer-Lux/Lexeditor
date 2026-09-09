#!/usr/bin/env python3
"""Print a read-only resource-family inventory for Chrono Trigger Steam."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from games.chrono_trigger.inventory import inventory_archive
from games.chrono_trigger.resources import ResourceArchive, ResourceArchiveError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inventory Chrono Trigger Steam resources.bin families")
    parser.add_argument("--game", required=True, type=Path, help="Chrono Trigger Steam install directory")
    parser.add_argument("--samples", type=int, default=40, help="Maximum samples per candidate family")
    parser.add_argument(
        "--peek-sizes", action="store_true",
        help="Also read each candidate block's decoded 4-byte declared payload size; gzip payloads are not decompressed",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    archive_path = args.game.expanduser().resolve() / "resources.bin"
    try:
        archive = ResourceArchive(archive_path)
        payload = inventory_archive(
            archive, sample_limit=args.samples, peek_declared_sizes=args.peek_sizes,
        )
    except (OSError, ValueError, ResourceArchiveError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
