# Chrono Trigger (Steam)

Lexeditor integration for the Windows Steam release (App ID `613830`).

## Current scope

- Detect the Steam install using `Chrono Trigger.exe` and `resources.bin`.
- Decode the `ARC1` archive stream, compressed index, and individual resources.
- Browse/search/classify archive paths without unpacking the whole archive.
- Create/select editable Chrono Trigger mod projects.
- Treat `resources.bin` as an immutable Vanilla source and layer project files over it.
- Edit Steam localization/message files under `Localize/<language>/msg/*.txt`.
- Edit `Game/field/Mapinfo/mapinfo_*.dat` scene headers: music, tilesets/assemblies, palette data, map/script IDs and scroll bounds.
- Edit existing scene exits from `MapJumpOffsetTbl.dat` + `MapJumpDataTbl.dat` without rewriting the offset table or changing record counts.
- Edit existing scene treasure from `TakaraOffsetTbl.dat` + `TakaraDataTbl.dat`, including decoded gold/item categories, without rewriting the offset table or changing record counts.
- Inspect Steam `Atel_*.dat` event structure: object count, 16 function slots/object, function bounds and raw bytecode previews. Opcode editing remains read-only.
- Edit all eight fixed 23-byte Steam overworld headers in `Game/common/bankc6.bin`, including chip sets, palettes, sprite sets, map/music/exit/script indices and assemblies.
- Follow each overworld header to its `Game/world/EventTable/EventTable_*.dat` and edit existing 8-byte exits, 3-byte triggers and 16-bit script-address entries. Count bytes, the null-trigger sentinel and vestigial records stay immutable.
- Follow each overworld header to its `Game/world/esl/Event_*.dat` and disassemble documented fixed-width world opcodes `0x00` through `0x52` read-only. Unknown PC/DS opcodes `0x53`/`0x54` stop decoding rather than guessing command boundaries.
- Expose an evidence-based Data Map that distinguishes structured, structurally decoded, partially known and raw-only data.
- Save every structured edit as a loose project overlay. **The installed `resources.bin` is never modified.**

Every shared-table write uses a source SHA-256 so stale edits fail instead of overwriting another change. Fixed-size table editors preserve all bytes outside the documented fields.

## Project/deployment model

CTExt hooks Chrono Trigger's resource loader and redirects archive-relative paths to loose files inside configured `mods/<name>/` folders. Lexeditor projects intentionally use those exact paths (`Game/...`, `Localize/...`). This is the normal deployment model; rebuilding `resources.bin` is not required.

Lexeditor currently creates/edits the loose-file project and discovers existing CTExt-style mod folders. Automatic CTExt installation and load-order configuration are still pending; no runtime DLL or CTExt configuration is silently modified.

## Validation

The dedicated Chrono Trigger workflow compiles every plugin module, validates the plugin descriptor, auto-discovers every `test_chrono_trigger_*.py` regression suite, runs `python app.py --game chrono-trigger --smoke` against a synthetic Steam install/ARC1 archive, and syntax-checks the editor JavaScript with Node.

The managed smoke test starts the real child service, reads ARC1 localization/scene resources, writes project overlays, verifies the Vanilla archive remains unchanged, checks the Data Map, and confirms the service releases its port on shutdown.

## Format evidence

The implementation is independently written against behavior documented by existing Chrono Trigger PC tooling rather than copying a third-party editor wholesale:

- ChronoMod: <https://github.com/jimzrt/ChronoMod> — open-source `resources.bin` reader/repacker for the Steam release.
- CTViewer: <https://github.com/GitExl/CTViewer> — reads Steam `resources.bin` directly and documents PC scene/world resource paths and structures, including scene headers, exits, treasure, overworld headers, overworld exits/triggers/script addresses, and the world-script opcode table.
- Temporal Redux: <https://github.com/OnemusCT/temporal-redux> — PC-aware event editing; documents Steam `Mapinfo` fields, `Atel` event compatibility and message-table handling.
- CTExt: <https://github.com/TheRealBiggs/ctext> — Steam runtime mod loader with loose-file and CTP resource overrides.

The Steam release uses install directory `Chrono Trigger`, executable `Chrono Trigger.exe`, main archive `resources.bin`, and App ID `613830`.

## Known next slices

1. Decode/integrate `Atel_*.dat` event opcodes incrementally, with round-trip tests before any command editor becomes writable.
2. Add map visualisation from the documented PC map/tile formats.
3. Add CTExt status/install/load-order management only with pinned, verified helper artifacts and recoverable configuration writes.
4. Inventory battle/item/enemy/tech resources from a current Steam archive and only add structured editors where current-format evidence is sufficient.
5. Keep archive rebuilding as a fallback/export path, not the default mod deployment path, and require real-install round-trip validation before enabling it.
