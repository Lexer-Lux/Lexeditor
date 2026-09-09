"""Chrono Trigger Steam coverage metadata layered over the core data map."""

from __future__ import annotations

import re

from .data import OverlayStore


WORLD_BANK = "Game/common/bankc6.bin"
_WORLD_TABLE_RE = re.compile(r"^Game/world/EventTable/EventTable_\d+\.dat$", re.IGNORECASE)
_WORLD_SCRIPT_RE = re.compile(r"^Game/world/esl/Event_\d+\.dat$", re.IGNORECASE)
_FIELD_SCRIPT_RE = re.compile(r"^Game/field/atel/Atel_\d+\.dat$", re.IGNORECASE)
_SCENE_MAP_RE = re.compile(r"^Game/field/MapTable/MapTable_\d+\.dat$", re.IGNORECASE)


def resource_override(path: str) -> dict | None:
    """Return classifications for integrations implemented outside data.py."""
    if path.casefold() == WORLD_BANK.casefold():
        return {"kind": "world-headers", "coverage": "structured", "status": "integrated", "target": "worlds"}
    if _WORLD_TABLE_RE.match(path):
        return {"kind": "world-navigation", "coverage": "structured", "status": "integrated", "target": "worlds"}
    if _WORLD_SCRIPT_RE.match(path):
        return {"kind": "world-script", "coverage": "structural", "status": "partial", "target": "worlds"}
    if _FIELD_SCRIPT_RE.match(path):
        return {"kind": "field-event-script", "coverage": "structural", "status": "partial", "target": "events"}
    if _SCENE_MAP_RE.match(path):
        return {"kind": "scene-map-layout", "coverage": "structural", "status": "integrated", "target": "scenes"}
    return None


def augment_data_map(store: OverlayStore, payload: dict) -> dict:
    """Add integrations that live outside the core data module."""
    result = dict(payload)
    rows = list(payload.get("rows", []))
    paths = [entry.path for entry in store.archive.entries]
    world_tables = sum(bool(_WORLD_TABLE_RE.match(path)) for path in paths)
    world_scripts = sum(bool(_WORLD_SCRIPT_RE.match(path)) for path in paths)
    field_scripts = sum(bool(_FIELD_SCRIPT_RE.match(path)) for path in paths)
    scene_maps = sum(bool(_SCENE_MAP_RE.match(path)) for path in paths)
    has_bank = any(path.casefold() == WORLD_BANK.casefold() for path in paths)

    for index, row in enumerate(rows):
        filename = str(row.get("filename", ""))
        if filename.startswith("Game/world/esl/"):
            rows[index] = {
                **row,
                "controls": f"{world_scripts} overworld scripts; documented opcodes 0x00–0x52 disassembled",
                "notes": "Known CTViewer opcode widths are decoded read-only. Disassembly stops at unknown PC/DS 0x53/0x54 or truncated data rather than guessing boundaries.",
                "status": "partial", "coverage": "structural", "openable": bool(world_scripts), "target": "worlds",
            }
        elif filename.startswith("Game/field/atel/"):
            rows[index] = {
                **row,
                "controls": f"{field_scripts} field event scripts: object/function layout plus Steam command-boundary disassembly",
                "notes": "PC argument widths and dynamic-length commands are decoded read-only. Ambiguous 0x9E/0x9F and malformed commands fail closed; command writing is not enabled.",
                "status": "partial", "coverage": "structural", "openable": bool(field_scripts), "target": "events",
            }

    insertion = next((index for index, row in enumerate(rows)
                      if str(row.get("filename", "")).startswith("Game/world/esl/")), len(rows))
    additions = [
        {
            "filename": "Game/field/MapTable/MapTable_*.dat",
            "controls": f"{scene_maps} scene map layouts: layer dimensions/tile IDs, scroll/blend header and RLE collision/property grid",
            "notes": "Structural map/collision visualisation is integrated read-only. Tileset artwork composition is a separate remaining layer.",
            "status": "integrated" if scene_maps else "partial", "coverage": "structural",
            "openable": bool(scene_maps), "target": "scenes",
        },
        {
            "filename": WORLD_BANK,
            "controls": "8 fixed 23-byte overworld headers: chips, palettes, sprite sets, map/music/exit/script indices and assemblies",
            "notes": "CTViewer documents the PC headers at 0xFD10 + worldIndex*23. Lexeditor edits those bytes in the loose project overlay only.",
            "status": "integrated" if has_bank else "partial", "coverage": "structured",
            "openable": has_bank, "target": "worlds",
        },
        {
            "filename": "Game/world/EventTable/EventTable_*.dat",
            "controls": f"{world_tables} overworld navigation tables: fixed exits, triggers and script-address entries",
            "notes": "Existing counted records are editable. Count bytes, null-trigger sentinel and vestigial records remain immutable.",
            "status": "integrated" if world_tables else "partial", "coverage": "structured",
            "openable": bool(world_tables), "target": "worlds",
        },
        {
            "filename": "Selected project overlay",
            "controls": "Override inventory, modified/added/redundant classification and stale-hash-protected revert",
            "notes": "Revert removes only the loose project copy. Vanilla ARC1 resources remain immutable.",
            "status": "integrated", "coverage": "project", "openable": True, "target": "changes",
        },
        {
            "filename": "<project>.ctp",
            "controls": "Deterministic CTExt ZIP export",
            "notes": "Sorted fixed-timestamp archive-relative project resources; editor/deployment metadata is excluded. No resources.bin repack is needed.",
            "status": "integrated", "coverage": "export", "openable": True, "target": "deployment",
        },
        {
            "filename": "Individual resources",
            "controls": "Decoded-size/SHA metadata, bounded UTF-8 text previews and image previews",
            "notes": "Direct inspection is capped at 32 MiB decoded; text preview is capped at 128 KiB. Unknown binaries remain download-only.",
            "status": "integrated", "coverage": "raw", "openable": True, "target": "resources",
        },
    ]
    rows[insertion:insertion] = additions
    result["rows"] = rows
    counts = dict(payload.get("counts", {}))
    counts.update({
        "worldHeaders": 8 if has_bank else 0,
        "worldEventTables": world_tables,
        "worldScripts": world_scripts,
        "fieldScripts": field_scripts,
        "sceneMaps": scene_maps,
    })
    result["counts"] = counts
    return result
