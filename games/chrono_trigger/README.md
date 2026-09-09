# Chrono Trigger (Steam)

Lexeditor integration for the Windows Steam release (App ID `613830`).

## Current scope

- Detect the Steam install using `Chrono Trigger.exe` and `resources.bin`.
- Decode the `ARC1` archive stream, compressed index, and individual resources.
- Browse/search/classify archive paths without unpacking the whole archive.
- Create/select editable Chrono Trigger mod projects.
- Treat `resources.bin` as an immutable Vanilla source and layer project files over it.
- Edit Steam localization/message files under `Localize/<language>/msg/*.txt`.
- Edit `Game/field/Mapinfo/mapinfo_*.dat` scene headers:
  - music
  - layer 1/2 and layer 3 tileset IDs
  - tileset assembly
  - palette and palette-animation IDs
  - map, chip-animation, and event-script IDs
  - the u16 field at offset `0x12`
  - four one-byte scroll bounds
- Expose an evidence-based Data Map that distinguishes structured, partially decoded, and raw-only data.
- Save every structured edit as a loose project overlay. **The installed `resources.bin` is never modified.**

## Project/deployment model

CTExt hooks Chrono Trigger's resource loader and can redirect archive-relative paths to loose files inside a configured `mods/<name>/` directory. Lexeditor projects intentionally use those exact paths (`Game/...`, `Localize/...`). This gives us a safer normal deployment path than rebuilding the game's archive.

Lexeditor currently creates and edits the loose-file project. Automatic CTExt installation and load-order configuration are still pending; no runtime helper is silently installed or modified.

## Format evidence

The implementation is independently written against behavior documented by existing Chrono Trigger PC tooling rather than copying a third-party editor wholesale:

- ChronoMod: <https://github.com/jimzrt/ChronoMod> — open-source `resources.bin` reader/repacker for the Steam release.
- CTViewer: <https://github.com/GitExl/CTViewer> — reads Steam `resources.bin` directly and documents PC map/world/scene resource paths and structures.
- Temporal Redux: <https://github.com/OnemusCT/temporal-redux> — PC-aware event editing; documents Steam `Mapinfo` fields, `Atel` event compatibility, and message-table handling.
- CTExt: <https://github.com/TheRealBiggs/ctext> — Steam runtime mod loader with loose-file and CTP resource overrides.

The Steam release uses install directory `Chrono Trigger`, executable `Chrono Trigger.exe`, main archive `resources.bin`, and App ID `613830`.

## Known next slices

1. Integrate structured `Atel_*.dat` field-event command editing using the proven PC event layout.
2. Add scene exits and treasure tables (`MapJump*`, `Takara*`).
3. Add world-map/event structures and map visualisation incrementally from CTViewer's documented PC layouts.
4. Add CTExt status/install/load-order management only with pinned, verified helper artifacts and recoverable writes.
5. Keep archive rebuilding as a fallback/export path, not the default mod deployment path, and require real-install round-trip validation before enabling it.
