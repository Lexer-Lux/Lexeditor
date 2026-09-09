"""Chrono Trigger Steam coverage metadata layered over the core data map."""

from __future__ import annotations

import re

from .data import OverlayStore


WORLD_BANK = "Game/common/bankc6.bin"
_WORLD_TABLE_RE = re.compile(r"^Game/world/EventTable/EventTable_\d+\.dat$", re.IGNORECASE)
_WORLD_SCRIPT_RE = re.compile(r"^Game/world/esl/Event_\d+\.dat$", re.IGNORECASE)


def resource_override(path: str) -> dict | None:
    """Return classifications for integrations implemented outside data.py."""
    if path.casefold() == WORLD_BANK.casefold():
        return {
            "kind": "world-headers",
            "coverage": "structured",
            "status": "integrated",
            "target": "worlds",
        }
    if _WORLD_TABLE_RE.match(path):
        return {
            "kind": "world-navigation",
            "coverage": "structured",
            "status": "integrated",
            "target": "worlds",
        }
    if _WORLD_SCRIPT_RE.match(path):
        return {
            "kind": "world-script",
            "coverage": "structural",
            "status": "partial",
            "target": "worlds",
        }
    return None


def augment_data_map(store: OverlayStore, payload: dict) -> dict:
    """Add current world integrations to the evidence-based Data Map."""
    result = dict(payload)
    rows = list(payload.get("rows", []))
    paths = [entry.path for entry in store.archive.entries]
    world_tables = sum(bool(_WORLD_TABLE_RE.match(path)) for path in paths)
    world_scripts = sum(bool(_WORLD_SCRIPT_RE.match(path)) for path in paths)
    has_bank = any(path.casefold() == WORLD_BANK.casefold() for path in paths)

    world_script_index = next(
        (index for index, row in enumerate(rows)
         if str(row.get("filename", "")).startswith("Game/world/esl/")),
        len(rows),
    )
    if world_script_index < len(rows):
        rows[world_script_index] = {
            **rows[world_script_index],
            "controls": f"{world_scripts} overworld scripts; fixed-width opcodes 0x00–0x52 disassembled",
            "notes": "Known CTViewer opcode widths are decoded read-only. Disassembly stops at unknown PC/DS opcodes 0x53/0x54 or truncated data rather than guessing boundaries.",
            "status": "partial",
            "coverage": "structural",
            "openable": bool(world_scripts),
            "target": "worlds",
        }

    additions = [
        {
            "filename": WORLD_BANK,
            "controls": "8 fixed 23-byte overworld headers: chips, palettes, sprite sets, map/music/exit/script indices and assemblies",
            "notes": "CTViewer documents the PC headers at 0xFD10 + worldIndex*23. Lexeditor edits those bytes in the loose project overlay only.",
            "status": "integrated" if has_bank else "partial",
            "coverage": "structured",
            "openable": has_bank,
            "target": "worlds",
        },
        {
            "filename": "Game/world/EventTable/EventTable_*.dat",
            "controls": f"{world_tables} overworld navigation tables: fixed exits, triggers and script-address entries",
            "notes": "Existing counted records are editable. Count bytes, null-trigger sentinel and vestigial records remain immutable.",
            "status": "integrated" if world_tables else "partial",
            "coverage": "structured",
            "openable": bool(world_tables),
            "target": "worlds",
        },
    ]
    rows[world_script_index:world_script_index] = additions
    result["rows"] = rows
    counts = dict(payload.get("counts", {}))
    counts.update({
        "worldHeaders": 8 if has_bank else 0,
        "worldEventTables": world_tables,
        "worldScripts": world_scripts,
    })
    result["counts"] = counts
    return result
