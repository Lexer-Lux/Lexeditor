# Chrono Trigger (Steam)

Initial Lexeditor integration for the Windows Steam release (App ID `613830`).

## Current scope

- Detect the Steam install using `Chrono Trigger.exe` and `resources.bin`.
- Open a managed Lexeditor child service.
- Decode the `ARC1` archive stream.
- Parse the gzip-compressed resource index.
- Browse/search resource paths, offsets, and stored sizes without unpacking the whole archive.
- Decode and decompress individual entries through the Python archive API.
- **Read-only:** the installed `resources.bin` is never modified.

## Format evidence

The implementation was independently written against behavior documented by existing Chrono Trigger PC tooling rather than importing third-party source code:

- ChronoMod: <https://github.com/jimzrt/ChronoMod> — open-source `resources.bin` reader/repacker for the Steam release.
- CTViewer: <https://github.com/GitExl/CTViewer> — consumes Steam `resources.bin` directly for PC map viewing.
- Temporal Redux: <https://github.com/OnemusCT/temporal-redux> — PC-aware Chrono Trigger editing/research tooling.

The current Steam depot identifies `Chrono Trigger.exe`, `resources.bin`, and install directory `Chrono Trigger`; the game is Steam App ID `613830`.

## Next slices

1. Inventory and classify high-value archive paths (battle, item, enemy, tech, text, map/event data).
2. Add evidence-backed Data Map entries for structures we can parse reliably.
3. Add project-overlay extraction/editing so original game files stay immutable.
4. Implement archive rebuilding only after round-trip fixtures and real-install validation are in place.
