"""Chrono Trigger Steam coverage metadata layered over the core data map."""

from __future__ import annotations

import re

from .data import OverlayStore


WORLD_BANK = "Game/common/bankc6.bin"
_WORLD_TABLE_RE = re.compile(r"^Game/world/EventTable/EventTable_\d+\.dat$", re.IGNORECASE)
_WORLD_SCRIPT_RE = re.compile(r"^Game/world/esl/Event_\d+\.dat$", re.IGNORECASE)
_FIELD_SCRIPT_RE = re.compile(r"^Game/field/atel/Atel_\d+\.dat$", re.IGNORECASE)
_SCENE_MAP_RE = re.compile(r"^Game/field/MapTable/MapTable_\d+\.dat$", re.IGNORECASE)
_SCENE_PALETTE_RE = re.compile(r"^Game/field/palette_bin/plt\d+\.bin$", re.IGNORECASE)
_WORLD_PALETTE_RE = re.compile(r"^Game/world/plt_bin/plt\d+\.bin$", re.IGNORECASE)


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
    if _SCENE_PALETTE_RE.match(path) or _WORLD_PALETTE_RE.match(path):
        return {"kind": "bgr555-palette", "coverage": "structured", "status": "integrated", "target": "resources"}
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
    scene_palettes = sum(bool(_SCENE_PALETTE_RE.match(path)) for path in paths)
    world_palettes = sum(bool(_WORLD_PALETTE_RE.match(path)) for path in paths)
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
                "controls": f"{field_scripts} field event scripts: object/function layout, PC command disassembly, semantics and control-flow diagnostics",
                "notes": "Existing fixed-width argument bytes can be edited through stale-hash-protected project overlays; named editors cover proven enemy/location/text/inventory/gold/party/audio/battle layouts. Opcode changes, insertion/deletion, pointer relocation and variable/unresolved commands remain read-only.",
                "status": "partial", "coverage": "structural + fixed-write", "openable": bool(field_scripts), "target": "events",
            }
        elif filename.startswith("CTExt mods/"):
            rows[index] = {
                **row,
                "controls": "Explicit loose-file deployment, audit, activation, deactivation and manifest-owned undeploy",
                "notes": "Lexeditor validates ctext.json, backs it up before load-order changes, never installs/replaces DLLs, never deletes direct mods/ source projects, and removes only manifest-owned deployed files.",
                "status": "integrated", "coverage": "deployment", "openable": True, "target": "deployment",
            }

    insertion = next((index for index, row in enumerate(rows)
                      if str(row.get("filename", "")).startswith("Game/world/esl/")), len(rows))
    additions = [
        {
            "filename": "Game/field/MapTable/MapTable_*.dat + referenced PC tilesets",
            "controls": f"{scene_maps} scene map layouts: dimensions/tile IDs, scroll/blend header, RLE collision grid and L1/L2 PNG raster export",
            "notes": "Structural map/collision view is integrated. tools/chrono_trigger_map.py renders actual PC L1/L2 artwork from BGSetTable + cg + ChipTable + BGR555 palette. Animated-chip playback, L3 artwork and main/sub-screen blend emulation remain future work.",
            "status": "integrated" if scene_maps else "partial", "coverage": "structural + raster",
            "openable": bool(scene_maps), "target": "scenes",
        },
        {
            "filename": "Game/field/palette_bin/plt*.bin + Game/world/plt_bin/plt*.bin",
            "controls": f"{scene_palettes + world_palettes} fixed 256-color BGR555 palettes",
            "notes": "Two-byte header and trailing data are preserved. Individual colors support raw BGR555 or RGB edits in project overlays; tools/chrono_trigger_palette.py provides show/set workflow.",
            "status": "integrated" if scene_palettes + world_palettes else "partial", "coverage": "structured",
            "openable": False, "target": "resources",
        },
        {
            "filename": WORLD_BANK,
            "controls": "8 fixed 23-byte overworld headers: chips, palettes, sprite sets, map/music/exit/script indices and assemblies",
            "notes": "CTViewer documents the PC headers at 0xFD10 + worldIndex*23. Lexeditor edits those bytes in the loose project overlay only. tools/chrono_trigger_map.py can render world L1/L2 from the referenced map/chip/palette resources.",
            "status": "integrated" if has_bank else "partial", "coverage": "structured + raster",
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
            "filename": "Actual resources.bin path families",
            "controls": "Index-only gameplay candidate inventory for battle/enemy/tech/item/shop/party reverse engineering",
            "notes": "tools/chrono_trigger_inventory.py derives candidates from the installed ARC1 index without decompressing payloads. Steam gameplay-stat editors are intentionally not claimed until current-format record layouts are independently evidenced.",
            "status": "integrated", "coverage": "research", "openable": False,
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
        "scenePalettes": scene_palettes,
        "worldPalettes": world_palettes,
    })
    result["counts"] = counts
    return result
