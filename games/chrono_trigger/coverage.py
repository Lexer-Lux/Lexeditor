"""Chrono Trigger Steam coverage metadata layered over the core data map."""

from __future__ import annotations

import re

from .data import OverlayStore


WORLD_BANK = "Game/common/bankc6.bin"
_WORLD_TABLE_RE = re.compile(r"^Game/world/EventTable/EventTable_\d+\.dat$", re.IGNORECASE)
_WORLD_SCRIPT_RE = re.compile(r"^Game/world/esl/Event_\d+\.dat$", re.IGNORECASE)
_FIELD_SCRIPT_RE = re.compile(r"^Game/field/atel/Atel_\d+\.dat$", re.IGNORECASE)
_SCENE_MAP_RE = re.compile(r"^Game/field/MapTable/MapTable_\d+\.dat$", re.IGNORECASE)
_SCENE_ANIM_RE = re.compile(r"^Game/field/BGAnime/bganimeinfo_\d+\.dat$", re.IGNORECASE)
_SCENE_L3_GFX_RE = re.compile(r"^Game/field/weather_bin/cg\d+\.bin$", re.IGNORECASE)
_SCENE_L3_ASSEMBLY_RE = re.compile(r"^Game/field/ChipTable/ChipTableBg3_\d+\.dat$", re.IGNORECASE)
_SCENE_PALETTE_RE = re.compile(r"^Game/field/palette_bin/plt\d+\.bin$", re.IGNORECASE)
_WORLD_PALETTE_RE = re.compile(r"^Game/world/plt_bin/plt\d+\.bin$", re.IGNORECASE)


def resource_override(path: str) -> dict | None:
    """Return classifications for integrations implemented outside data.py."""
    if path.casefold() == WORLD_BANK.casefold():
        return {"kind": "world-headers", "coverage": "structured + raster", "status": "integrated", "target": "worlds"}
    if _WORLD_TABLE_RE.match(path):
        return {"kind": "world-navigation", "coverage": "structured", "status": "integrated", "target": "worlds"}
    if _WORLD_SCRIPT_RE.match(path):
        return {"kind": "world-script", "coverage": "structural", "status": "partial", "target": "worlds"}
    if _FIELD_SCRIPT_RE.match(path):
        return {"kind": "field-event-script", "coverage": "structural + fixed-write", "status": "partial", "target": "events"}
    if _SCENE_MAP_RE.match(path):
        return {"kind": "scene-map-layout", "coverage": "structural + raster", "status": "integrated", "target": "scenes"}
    if _SCENE_ANIM_RE.match(path):
        return {"kind": "scene-chip-animation", "coverage": "structural", "status": "partial", "target": "scenes"}
    if _SCENE_L3_GFX_RE.match(path):
        return {"kind": "scene-l3-graphics", "coverage": "raster", "status": "integrated", "target": "scenes"}
    if _SCENE_L3_ASSEMBLY_RE.match(path):
        return {"kind": "scene-l3-assembly", "coverage": "raster", "status": "integrated", "target": "scenes"}
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
    scene_animations = sum(bool(_SCENE_ANIM_RE.match(path)) for path in paths)
    scene_l3_graphics = sum(bool(_SCENE_L3_GFX_RE.match(path)) for path in paths)
    scene_l3_assemblies = sum(bool(_SCENE_L3_ASSEMBLY_RE.match(path)) for path in paths)
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
                "controls": f"{field_scripts} field event scripts: PC disassembly/control flow plus named fixed-width item, comparison, memory, bit, PC-extended, call, object/facing/property, movement/follow, location/party/screen, audio and other proven editors",
                "notes": "Desktop Events and tools/chrono_trigger_event.py edit only proven fixed-width argument bytes through stale-hash-protected project overlays. Current proven additions include 0x12–0x16 comparisons, including canonical bank-7F page/operator packing for 0x16; narrow 0x1C bank result storage at 0x7F0000–0x7F00FF; bank assignments 0x53/54/56/58/59 with constructor-evidenced ranges; script-memory bit ops 0x63/64/69/6B/6F plus canonical bank-7F 0x65/66; PC-only raw-slot 0x3A/3D/3E/45/46/6E/70/74/78, with 0x6E exposed as raw extended slot + value + comparator + validated jump; 0x02–0x07 calls; doubled object controls 0x0A/0B/0C/7C/7D; doubled facing/result targets 0x23/24/A8/A9; directional NPC-facing 0x1E/1F/25/26 limited to the live 0x00–0x32 menu domain; 0x0D/0x0E known property bits with unknown-bit preservation; movement/follow 0x7A/8F/94–99/9A/9D/A0/A1/B5/B6; D9/E2/E7/F4 party/location/screen controls; EB song volume; and compact 29/82/C8 operands. Raw coordinates stay labeled as bytes unless units are independently evidenced. EC is dynamically disassembled by documented Sound-menu widths with read-only known-form semantics. PC parser contracts govern 0x2E/0x88/0x4E where generic menus differ. F1 stops fail-closed because public PC parser/table and live menu disagree on its one-vs-two-argument boundary. Ambiguous 0x48–4D/60/61/67/75/76/77/7B/27/28/8D/8E/92/9C/9E/9F and dynamic/unresolved writes remain read-only. Changed jump bytes must target decoded command boundaries. Opcode changes, insertion/deletion and pointer relocation remain unsupported.",
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
            "filename": "Game/field/MapTable/MapTable_*.dat + referenced PC L1/L2/L3 tilesets",
            "controls": f"{scene_maps} scene map layouts: structural tiles/collision plus desktop and CLI L1/L2/L3 PC raster previews and read-only render diagnostics",
            "notes": "L1/L2 render from BGSetTable + map_bin/cg + ChipTable; L3 follows CTViewer's PC-only weather_bin/cg + scene-indexed ChipTableBg3 path. MapTable main/sub/effect bits are decoded using CTViewer's PC labels, while PrioMap stays raw because CTViewer itself still calls its four PC bytes unknown layer-priority data. BGAnime descriptors are decoded separately, but animation playback and main/sub-screen blend/priority composition remain explicitly unsupported.",
            "status": "integrated" if scene_maps else "partial", "coverage": "structural + raster",
            "openable": bool(scene_maps), "target": "scenes",
        },
        {
            "filename": "Game/field/BGAnime/bganimeinfo_*.dat + BGSetTable animation slot",
            "controls": f"{scene_animations} PC chip-animation descriptors decoded as four-chip destination/source groups with per-frame duration bytes",
            "notes": "The PC descriptor's first byte declares the animation count. Destination/source offsets are converted with offset/32; duration meaning comes from the upper nibble (0x10/0x20/0x40/0x80 = 16/12/8/4 ticks) while the lower nibble is preserved as unknown. Runtime phase and initial-frame behavior are not inferred, so playback remains unsupported.",
            "status": "partial", "coverage": "structural", "openable": bool(scene_animations), "target": "scenes",
        },
        {
            "filename": "Game/field/weather_bin/cg*.bin + Game/field/ChipTable/ChipTableBg3_*.dat",
            "controls": f"{scene_l3_graphics} L3 graphics sets and {scene_l3_assemblies} scene-indexed L3 assemblies used by isolated raster preview",
            "notes": "Current Steam/PC L3 rendering follows CTViewer's PC backend: a four-byte cg header is skipped before nibble unpacking, L3 assemblies contain 256 four-corner tiles with three-byte PC corner records, and palette indices select 4-color groups.",
            "status": "integrated" if scene_l3_graphics and scene_l3_assemblies else "partial",
            "coverage": "raster", "openable": bool(scene_l3_graphics or scene_l3_assemblies), "target": "scenes",
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
            "controls": "8 fixed 23-byte overworld headers plus desktop and CLI L1/L2 PC raster previews",
            "notes": "CTViewer documents the PC headers at 0xFD10 + worldIndex*23. Header edits stay in the loose project overlay. The desktop Worlds Map tab and tools/chrono_trigger_map.py render isolated L1/L2 from referenced map/chip/palette resources without claiming blend/animation emulation.",
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
            "controls": "Read-only gameplay family inventory plus bounded selected-family/path payload probe for battle/enemy/tech/item/shop/party reverse engineering",
            "notes": "tools/chrono_trigger_inventory.py defaults to ARC1 index metadata only and can optionally peek the decoded four-byte declared payload-size prefixes without inflating candidate data; repeated directory/size groups become probe-ready recommendations. tools/chrono_trigger_probe.py then requires an explicit family (optionally a path prefix), enforces resource/stored/declared-size caps before decompression, and reports only structural same-size byte differences. No gameplay-stat editor is claimed from these diagnostics alone.",
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
        "sceneChipAnimations": scene_animations,
        "sceneL3Graphics": scene_l3_graphics,
        "sceneL3Assemblies": scene_l3_assemblies,
        "scenePalettes": scene_palettes,
        "worldPalettes": world_palettes,
    })
    result["counts"] = counts
    return result
