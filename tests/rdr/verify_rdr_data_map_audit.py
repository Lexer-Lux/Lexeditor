"""Audit every generated RDR1 Data Map row against runtime capability gating.

The generated map is research/index evidence, not proof of an editor. This check
loads every row and verifies that only explicit format-specific interfaces may
promote a row above Not integrated. Dynamic parser-backed promotion (shops and
PC STRTBL) is covered separately with synthetic prepared-data tests.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.rdr import loot_script, server


def _rows() -> list[dict]:
    path = ROOT / "plugins" / "rdr" / "data_map.generated.json"
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = document.get("rows", document.get("files", [])) if isinstance(document, dict) else document
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("RDR1 generated Data Map has no rows")
    return rows


def _filename(row: dict) -> str:
    return str(row.get("filename") or row.get("file") or "").strip()


def _extension(filename: str) -> str:
    tail = filename.split(":/", 1)[-1]
    return PurePosixPath(tail).suffix.casefold() or "(none)"


def _archive(filename: str) -> str:
    return filename.split(":/", 1)[0] if ":/" in filename else "(project/other)"


def _capability(status: str, target: str, controls: str) -> dict:
    return {
        "filename": "",
        "controls": controls,
        "notes": "Explicit audit capability.",
        "coverage": "structured",
        "status": status,
        "target": target,
        "openable": True,
    }


def main() -> int:
    rows = _rows()
    names = [_filename(row) for row in rows]
    if any(not name for name in names):
        raise RuntimeError("RDR1 generated Data Map contains a row without a filename")
    duplicates = [name for name, count in Counter(name.casefold() for name in names).items() if count > 1]
    if duplicates:
        raise RuntimeError(f"RDR1 generated Data Map contains duplicate filenames: {duplicates[:8]}")

    interfaces: dict[str, dict] = {}

    loot_name = f"game/content.rpf:/{loot_script.ARCHIVE_PATH}"
    interfaces[loot_name.casefold()] = _capability(
        "partial", "loot", "Verified corpse-loot WSC item-enum call sites")

    for definition in server.INVENTORY_SOURCES.values():
        name = f"game/content.rpf:/{definition['relative'].as_posix()}"
        interfaces[name.casefold()] = _capability(
            "partial", "items", "Direct scalar inventory XML fields")

    # These project files are format-specific typed editors when they exist.
    interfaces["lexerrdr.ini"] = _capability(
        "integrated", "settings", "Typed LexerRDR runtime settings")
    interfaces["lexerrdr.loot.json"] = _capability(
        "integrated", "loot", "Schema-validated runtime loot override")

    normalized = server._normalize_data_map_rows(rows, interfaces=interfaces)
    promoted = [row for row in normalized if row["status"] != "not-integrated"]
    unexpected = [
        row for row in promoted
        if row["filename"].casefold() not in interfaces
    ]
    if unexpected:
        raise RuntimeError(
            "Generated research rows were promoted without an explicit interface: "
            + ", ".join(row["filename"] for row in unexpected[:8])
        )

    present = {name.casefold() for name in names}
    required = {
        loot_name.casefold(),
        *(
            f"game/content.rpf:/{definition['relative'].as_posix()}".casefold()
            for definition in server.INVENTORY_SOURCES.values()
        ),
    }
    missing = sorted(required - present)
    if missing:
        raise RuntimeError("Expected RDR1 capability rows are absent: " + ", ".join(missing))

    non_loot_wsc = [
        row for row in normalized
        if _extension(row["filename"]) == ".wsc"
        and row["filename"].casefold() != loot_name.casefold()
    ]
    if any(row["status"] != "not-integrated" or row["target"] for row in non_loot_wsc):
        raise RuntimeError("An unrelated WSC was promoted above Not integrated")

    ps3_strings = [
        row for row in normalized
        if row["filename"].casefold().endswith("_ps3.strtbl")
    ]
    if any(row["status"] != "not-integrated" or row["target"] for row in ps3_strings):
        raise RuntimeError("A PS3 STRTBL duplicate was promoted in the PC plugin")

    summary = {
        "rows": len(rows),
        "archives": dict(sorted(Counter(_archive(name) for name in names).items())),
        "extensions": dict(sorted(Counter(_extension(name) for name in names).items())),
        "generatedStatuses": dict(sorted(Counter(
            str(row.get("status", "unspecified")).casefold() for row in rows
        ).items())),
        "runtimePromotedByStaticCapabilities": dict(sorted(Counter(
            row["status"] for row in promoted
        ).items())),
        "unrelatedWscNotIntegrated": len(non_loot_wsc),
        "ps3StringTablesNotIntegrated": len(ps3_strings),
        "dynamicCapabilitiesTestedElsewhere": ["parsed PC STRTBL", "ShopInventory WGD", "protected RBF0 scalars"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("RDR1 generated Data Map audit passed: every row requires explicit runtime capability evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
