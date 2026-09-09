#!/usr/bin/env python3
"""Run a bounded read-only gameplay-family probe on Chrono Trigger Steam."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from games.chrono_trigger.inventory import CANDIDATE_KEYWORDS
from games.chrono_trigger.probe import probe_family
from games.chrono_trigger.resources import ResourceArchive, ResourceArchiveError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe a bounded Chrono Trigger Steam resource family for structural byte patterns"
    )
    parser.add_argument("--game", required=True, type=Path, help="Chrono Trigger Steam install directory")
    parser.add_argument("--family", required=True, choices=tuple(CANDIDATE_KEYWORDS), help="Candidate family")
    parser.add_argument("--limit", type=int, default=12, help="Maximum candidate resources to decompress")
    parser.add_argument("--bytes", dest="byte_window", type=int, default=128, help="Prefix/comparison byte window")
    parser.add_argument(
        "--max-payload", type=int, default=1024 * 1024,
        help="Skip entries whose declared uncompressed size exceeds this many bytes",
    )
    parser.add_argument(
        "--max-stored", type=int, default=1024 * 1024,
        help="Skip entries whose compressed ARC1 block exceeds this many bytes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    archive_path = args.game.expanduser().resolve() / "resources.bin"
    try:
        archive = ResourceArchive(archive_path)
        payload = probe_family(
            archive,
            args.family,
            limit=args.limit,
            byte_window=args.byte_window,
            max_payload_bytes=args.max_payload,
            max_stored_bytes=args.max_stored,
        )
    except (OSError, ValueError, ResourceArchiveError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
