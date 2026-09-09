# #406 — Add Final Fantasy VII Remake Intergrade plugin

## Current requirements

- Detect installed Steam/Epic FF7 Remake Intergrade.
- Integrate gameplay DataObjects as structured shared-UI controls and expose Data Map.
- Integrate localized `GameContents/Text` resources without bundling proprietary text dumps.
- Preserve installed archives and unknown bytes; save to a project overlay only.
- Build and explicitly deploy a loadable mod PAK.
- Theme the editor as an FF7R surface, using installed-game UI assets where they can be decoded safely and a proprietary-data-free fallback otherwise.
- Verify parser/write/theme behavior without committing proprietary fixtures.

## Implementation state

Candidate implementation lives on `feature/ff7-remake-plugin`.

- `repak` v0.2.3 is a pinned installable helper; FF7R's `../../../` PAK mount point is explicit.
- PAK indexes scan paired `End/Content/GameContents/DataObject` and `End/Content/GameContents/Text` assets.
- `.uasset`/`.uexp` pairs are extracted only when opened.
- Game Data maps booleans, numeric values, floats, FNames and fixed arrays to typed controls. Arbitrary DataObject FStrings remain read-only.
- Text resources have a separate language/resource editor supporting variable-length ASCII/UTF-16 main and existing sub-entry text.
- Installed `Resident_TxtRes` data resolves `$...` text IDs to readable local names without committing Square Enix text data.
- Saves use source/project SHA-256 conflict checks, atomic project writes and binary readback verification under `<project>/content`.
- Build creates `<project>/build/Lexeditor-FF7R_P.pak`; Deploy separately copies it to `End/Content/Paks/~mods`.
- Semantic item-price/carry-cap, enemy-loot, encounter, graphics, No More Cheats and Better Lock-on surfaces now sit on top of the installed-data layer; their issue-specific installed-game acceptance remains tracked on the child issues.
- Native runtime infrastructure and fail-closed installed-build probes exist for runtime-only features; unresolved authoritative hooks/state semantics remain child-issue blockers rather than guessed mutations.
- The FF7R editor has a plugin-local dark blue/cyan glass-HUD fallback theme and a private installed-theme asset pipeline. Browser-ready local fonts/images/audio can be copied only into Lexeditor's user-data cache; arbitrary files and cooked Unreal blobs are never exposed as web assets.
- The documented installed `SystemFontNormal4K` glyph UEXP plus `U_Com_JP_SystemFontNormal4K-01` 2048x2048 BC5 atlas can be validated and decoded locally. The resulting PNG + glyph metrics render shell tabs and detail titles with the game's actual bitmap font when those exact assets are present. No Square Enix font data is committed.
- Shared semantic UI sound slots (`confirm`, `back`, `move`, `launch`, `exit`, `save`) are wired into the theme contract. Direct browser-ready installed audio is supported; ordinary cooked FF7R menu audio is still discovery-only until a validated SoundWave decoder/source mapping is implemented.
- Synthetic fixtures exercise gameplay parsing/writes, text-ID resolution, variable-length Unicode text writes, malformed input, theme fallback/asset confinement, documented bitmap-font parsing/cache behavior and managed-service routes without storing game binaries.

## Tracked FF7R follow-ups

- #413 — configurable cutscene speed multiplier. Source runtime logic exists; installed-build hook/timing validation remains required.
- #414 — player-controlled minimap. Runtime/input/UI evidence exists; installed state-transition validation remains required.
- #415 — editable item prices. Semantic editor exists; installed-game shop acceptance remains required.
- #416 — editable enemy drops and drop chances. Semantic editor exists; installed-game drop/steal acceptance remains required.
- #424/#425/#427/#428/#430 and the other open FF7R child issues retain their own source/runtime blockers and acceptance state.

## Evidence / next work

FF7R-specific CI covers Python syntax, editor/theme JavaScript syntax, plugin/service descriptor validation, all `test_ff7r_*.py` regressions and managed-service smoke on Windows and Linux.

The theme implementation is source-verifiable but not visually accepted from CI. Installed acceptance must confirm the FF7R palette/layout in the real desktop WebView, successful `SystemFontNormal` discovery/decode on a current installed build, readable atlas-rendered labels at normal/high DPI, and any menu SFX/texture overrides that are actually decoded from the user's copy. Cooked menu textures and SoundWave assets remain an explicit next theming frontier rather than being misrepresented as already usable browser files.

### BLOCKED WITHOUT LOCAL FILE ACCESS — cooked FF7R UI assets

Finishing cooked FF7R menu texture and UI-SFX reuse requires direct filesystem access to a real local FF7R installation. An agent/session that cannot read the user's installed FF7R files **must refuse to claim or mark this item complete**: do not guess asset paths, pixel formats, Wwise/SoundWave mapping, codecs, or acceptance results from source/CI alone. Leave this item blocked until local file access is available.

When local access is available:

1. Inventory the installed menu/UI PAK assets and record the exact texture/audio source paths plus formats used by the current build.
2. Implement the narrow local-only decoders/converters needed for those verified assets; never bundle or redistribute Square Enix source assets.
3. Wire the decoded textures/SFX into `games/ff7r/theme.py` / `theme.js` and keep the authored palette as a fallback; derive color tokens from real assets only where the local evidence supports it.
4. Add proprietary-data-free decoder fixtures plus installed-game smoke/visual/audio acceptance.
5. Mark this frontier complete only after the actual installed build proves texture rendering, UI SFX playback, cache confinement, and fallback behavior.

Live game acceptance remains separate: actual installed PAK indexing, representative real DataObject/text parsing, semantic gameplay effects, game load, deployed-value effects and theme appearance must be checked on an installed copy before #406 or its follow-ups are considered complete.
