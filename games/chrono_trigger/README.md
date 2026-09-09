# Chrono Trigger (Steam)

Lexeditor integration for the Windows Steam release (App ID `613830`). The plugin is intentionally PC-format-first: SNES offsets are not promoted to Steam editors unless the corresponding PC resource layout is independently evidenced.

## Safety model

`resources.bin` is an immutable Vanilla source. Every edit is written to an archive-relative loose project path (`Game/...`, `Localize/...`) compatible with CTExt. Fixed-size shared-table writes use SHA-256 stale-write checks and preserve bytes outside documented fields.

The plugin does **not**:

- rewrite the installed `resources.bin`;
- insert/delete field-event commands or relocate Atel pointers;
- install or replace CTExt DLLs;
- delete a project that already lives directly under `mods/`;
- invent Steam enemy/item/tech stat layouts from SNES offsets.

## Desktop editor coverage

The managed Chrono Trigger editor currently provides:

- Steam install detection (`Chrono Trigger.exe`, `resources.bin`).
- Read-only `ARC1` archive decoding, search and classification.
- Bounded per-resource metadata/text/image previews.
- Editable localization/message resources under `Localize/<language>/msg/*.txt`.
- Editable 24-byte scene headers (`Game/field/Mapinfo/mapinfo_*.dat`).
- Editable existing scene exits (`MapJumpOffsetTbl.dat` + `MapJumpDataTbl.dat`), fixed 8-byte records; offset/count tables remain immutable.
- Editable existing treasure records (`TakaraOffsetTbl.dat` + `TakaraDataTbl.dat`), fixed 6-byte records; gold/item/category meaning is decoded.
- Scene MapTable structural view: L1/L2/L3 dimensions/tile IDs, scroll/blend header and RLE collision/property grid.
- Field-event inspector for `Atel_*.dat`: object count, 16 function slots/object, function bounds, PC command disassembly, semantic summaries and jump/fallthrough diagnostics.
- All eight editable fixed 23-byte overworld headers in `Game/common/bankc6.bin`.
- Editable existing overworld exits, triggers and script-address entries in `Game/world/EventTable/EventTable_*.dat`.
- Read-only overworld script disassembly for documented `Game/world/esl/Event_*.dat` opcodes `0x00`–`0x52`; unknown PC/DS `0x53`/`0x54` stop decoding instead of guessing.
- Localized labels for scenes, items, player characters, world names and world exits where the corresponding Steam message resource exists.
- Project Changes view: added/modified/redundant overrides plus stale-hash-protected revert of only the loose project copy.
- Deterministic `.ctp` project export.
- CTExt status + project integrity audit + explicit deployment/activation. DLL installation remains manual; deactivate/undeploy are currently CLI operations.
- Evidence-based Data Map reflecting structured, structural, raw, deployment and research coverage.

## Fixed-width field-event writes

Field event command editing is intentionally narrower than event disassembly. `event_edit.py` can replace the exact argument bytes of an existing fixed-width command without changing opcode, byte length, function pointers or object count. Variable/unresolved commands remain read-only.

`field_editors.py` adds named patches for PC layouts that are already explicit in Temporal Redux/PC tooling, including:

- LoadEnemy (`0x83`): enemy ID, slot, static flag;
- ChangeLocation (`0xDC`–`0xE1`): scene, facing, destination X/Y;
- textbox/decision commands (`0xBB`, `0xC0`–`0xC4`): string index/flags;
- CheckInventory (`0xC9`): item ID + jump;
- gold commands (`0xCC`–`0xCE`);
- party/player-ID checks and mutations;
- sound/music IDs (`0xE8`, `0xEA`);
- battle flags (`0xD8`), preserving unspecified bits.

These writes are currently exposed through `tools/chrono_trigger_event.py`; the desktop event view remains an inspection surface until the same named schemas are wired into UI controls.

## Map rendering

The structural map view is complemented by pure-Python raster exporters that use the actual PC asset chain rather than approximating SNES rendering.

### Scene L1/L2

`scene_render.py` follows:

`mapinfo` → `BGSetTable` → `cg*.bin` packed 4bpp sheets → PC 3-byte `ChipTable` corners → `plt*.bin` BGR555 palette → `MapTable` tile IDs.

L1/L2 are rendered separately. Animated chip playback, L3 artwork and main/sub-screen blend/priority emulation are explicitly not claimed yet.

### Overworld L1/L2

`world_render.py` follows the 23-byte world header to:

- `Game/world/Map/Map_*.dat` (fixed 96×64 L1 and L2 tile maps),
- eight `chipL12_*` graphics sheets,
- `Game/world/Chip/Chip_*.dat` assembly,
- `Game/world/plt_bin/plt*.bin` palette.

Output is an isolated 1536×1024 L1 or L2 raster.

Use `tools/chrono_trigger_map.py --scene ...` or `--world ...` to export PNGs.

## Palette editing

`palettes.py` decodes and edits the proven PC palette layout: a preserved two-byte header followed by 256 little-endian BGR555 colors. Scene and world palettes support raw BGR555 or RGB changes, stale-hash protection, and fixed-size overlay writes.

Use `tools/chrono_trigger_palette.py` for `show` / `set` workflow. The raster exporters automatically consume project palette overrides.

## Project/export/deployment tools

- `tools/chrono_trigger_project.py`: project change inventory, safe revert and deterministic CTP export.
- `tools/chrono_trigger_ctext.py`: `status`, `audit`, `deploy`, `deactivate`, `undeploy`.
- `tools/chrono_trigger_event.py`: event `show`, exact fixed-width `set-args`, and named `set-fields`.
- `tools/chrono_trigger_palette.py`: scene/world palette `show` / `set`.
- `tools/chrono_trigger_map.py`: scene/world L1/L2 PNG rendering.
- `tools/chrono_trigger_inventory.py`: index-only resource-family discovery against a real Steam `resources.bin`.

CTExt deployment validates the documented `mods.enabled` / `mods.load_order` config shape and creates `ctext.json.lexeditor.bak` before its first load-order mutation. Mirrored deployments have an ownership manifest. Redeploy/undeploy removes only manifest-owned files; unrelated files in the same destination survive. A source project already stored under `mods/<name>` is never deleted.

## Integrity audit

Deployment preflight scans every scene header, not the UI's paged 250-row window. It checks scene→Atel and world→EventTable/script references, decodes each unique referenced field event, reports partial disassembly, validates documented relative jump destinations against decoded command boundaries, rejects symlinked project content, and blocks deployment on malformed structured resources.

## Validation

`.github/workflows/chrono-trigger-checks.yml`:

- installs the host smoke's Pillow/fonttools import dependencies;
- compiles every plugin/CLI module;
- validates the plugin descriptor;
- auto-discovers every `test_chrono_trigger_*.py` suite;
- runs the real managed plugin smoke against a synthetic ARC1 Steam install;
- syntax-checks editor JavaScript with Node.

Regression coverage includes ARC1 decoding, overlays/stale writes, scene/world fixed tables, field/world disassembly, event semantics/flow/fixed writes, maps/collision, actual scene/world raster pixels, BGR555 palettes, CTP determinism, CTExt ownership lifecycle, project changes, resource previews, labels and the resource-family inventory.

## Format evidence

Implementation is independently written against publicly documented PC behavior:

- ChronoMod — `resources.bin` format: <https://github.com/jimzrt/ChronoMod>
- CTViewer — PC scene/world/maps/tilesets/palettes/scripts: <https://github.com/GitExl/CTViewer>
- Temporal Redux — PC Atel command widths/overrides and message handling: <https://github.com/OnemusCT/temporal-redux>
- CTExt — loose-file/CTP runtime loading and config semantics: <https://github.com/TheRealBiggs/ctext>

## Remaining high-value work

1. Wire named fixed-width Atel editors into the desktop Events UI; retain raw/variable commands as read-only.
2. Add scene L3/animated-tile rendering and correct PC main/sub-screen priority/blend composition.
3. Add raster previews to the desktop Map views (the renderers currently export through CLI).
4. Run `tools/chrono_trigger_inventory.py` against a current real Steam install and reverse-engineer battle/enemy/item/tech stat resources from the discovered PC paths before adding gameplay-stat editors.
5. Treat archive rebuilding only as a fallback/export experiment after real-install round-trip validation; CTExt loose files/CTP remain the default deployment path.
