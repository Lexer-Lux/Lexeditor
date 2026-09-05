"""Regression contract for RDR editor-data cache reuse (GitHub #71)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.rdr import extractor  # noqa: E402


def make_cache(root: Path) -> tuple[dict, dict, dict]:
    xml_files = (
        root / extractor.TUNING_CACHE_NAME / extractor.KNOWN_TUNING_XML,
        root / extractor.CONTENT_CACHE_NAME / extractor.INVENTORY_XML,
        root / extractor.CONTENT_CACHE_NAME / extractor.DLC_INVENTORY_XML,
    )
    for path in xml_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<root><entry /></root>\n", encoding="utf-8")
    packed = (
        root / extractor.GRINGO_PACKED_CACHE_NAME / "gringores" / "armadillo.wgd"
    )
    unpacked = (
        root / extractor.GRINGO_UNPACKED_CACHE_NAME / "gringores" / "armadillo.wgd"
    )
    packed.parent.mkdir(parents=True)
    unpacked.parent.mkdir(parents=True)
    packed.write_bytes(b"RSC\x85packed")
    unpacked.write_bytes(b"\x40\x00unpacked")
    records = {"source": "unchanged"}
    tool = {"tool": "unchanged"}
    manifest = {
        "version": 3,
        "sources": records,
        "tool": tool,
        "fileCounts": {
            "tuning": extractor.MINIMUM_FILE_COUNT,
            "inventory": 2,
            "gringoPacked": extractor.GRINGO_FILE_COUNT,
            "gringoUnpacked": extractor.GRINGO_FILE_COUNT,
        },
    }
    return records, tool, manifest


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-cache-", ignore_cleanup_errors=True) as temp:
        root = Path(temp)
        records, tool, manifest = make_cache(root)
        assert extractor._valid_cache(root, records, tool, manifest)

        tuning_xml = root / extractor.TUNING_CACHE_NAME / extractor.KNOWN_TUNING_XML
        good_xml = tuning_xml.read_bytes()
        tuning_xml.write_text("<broken>", encoding="utf-8")
        assert not extractor._valid_cache(root, records, tool, manifest)
        tuning_xml.write_bytes(good_xml)

        packed = (
            root / extractor.GRINGO_PACKED_CACHE_NAME / "gringores" / "armadillo.wgd"
        )
        packed.write_bytes(b"NOT-RSC")
        assert not extractor._valid_cache(root, records, tool, manifest)
        packed.write_bytes(b"RSC\x85packed")

        unpacked = (
            root / extractor.GRINGO_UNPACKED_CACHE_NAME / "gringores" / "armadillo.wgd"
        )
        unpacked.unlink()
        assert not extractor._valid_cache(root, records, tool, manifest)

    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Lexeditor"
    installations = local / "game-installations.json"
    data_root = local / "game-data" / "rdr"
    if installations.is_file() and (data_root / "manifest.json").is_file():
        payload = json.loads(installations.read_text(encoding="utf-8"))
        game_root = Path(payload["games"]["rdr"]["root"])
        before = {path.name for path in data_root.glob("*.previous-*")}
        original_extract = extractor._extract

        def reject_extract(*_args, **_kwargs) -> None:
            raise AssertionError("unchanged RDR data must not be extracted again")

        extractor._extract = reject_extract
        try:
            for _ in range(2):
                result = extractor.ensure_rdr_data(
                    game_root, data_root, lambda *_progress: None
                )
                assert result.get("version") == 3
        finally:
            extractor._extract = original_extract
        after = {path.name for path in data_root.glob("*.previous-*")}
        assert after == before, "cache reuse created a .previous-* directory"

    print("RDR cache format, mutation, and zero-reextraction contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
