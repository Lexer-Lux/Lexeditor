"""Verify the API that serves the world map's own sections."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import formats  # noqa: E402
from plugins.ff8.plugin import FF8Session  # noqa: E402

# What each section holds in the installed game, measured in
# tests/ff8/verify_ff8_world_scripts.py, verify_ff8_world_positions.py and
# verify_ff8_world_texts.py. This check is about the route answering with those
# same sections, so the counts must agree with those checks.
EXPECTED = {"playerScripts": 38, "eventScripts": 92, "spawnScripts": 20,
            "spawnPositions": 64, "trainExits": 3, "vehicleWarps": 4, "dialog": 151}


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-world-extra-",
                                          ignore_cleanup_errors=True)
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            seen = {}
            for kind, expected in EXPECTED.items():
                with urlopen(f"{session.url}/api/world-extra?kind={kind}&dataset=vanilla",
                             timeout=120) as response:
                    payload = json.load(response)
                assert payload["kind"] == kind, payload
                count = payload.get("count", len(payload.get("rows", [])))
                assert count == expected, (kind, count, expected)
                assert payload["rows"], kind
                # Each row carries what its own check proved: a script's byte
                # count, a position's coordinates, or a dialog string.
                first = payload["rows"][0]
                if kind == "dialog":
                    assert isinstance(first["text"], str) and first["text"], first
                elif kind in ("spawnPositions", "trainExits"):
                    assert "x" in first and "y" in first, first
                else:
                    assert first["bytes"] > 2, first
                    assert "sha256" in first, first
                seen[kind] = count
            # A kind nobody serves is refused, and the message names the kinds.
            try:
                formats.world_extra("nope")
            except ValueError as error:
                assert "unknown world section" in str(error).lower(), error
            else:
                raise AssertionError("an unknown world section was served")
            print(json.dumps({"sections": seen}, ensure_ascii=True))
        return 0
    finally:
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
