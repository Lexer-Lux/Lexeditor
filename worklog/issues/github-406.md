# #406 — Add Final Fantasy VII Remake Intergrade plugin

## Current requirements

- Detect installed Steam/Epic FF7 Remake Intergrade.
- Integrate gameplay DataObjects as structured shared-UI controls and expose Data Map.
- Integrate localized `GameContents/Text` resources without bundling proprietary text dumps.
- Preserve installed archives and unknown bytes; save to a project overlay only.
- Build and explicitly deploy a loadable mod PAK.
- Verify parser/write behavior without committing proprietary fixtures.

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
- Synthetic fixtures exercise gameplay parsing/writes, text-ID resolution, variable-length Unicode text writes, malformed input and managed-service save/readback without storing game binaries.

## Tracked FF7R follow-ups

- #413 — configurable cutscene speed multiplier. Base cutscene playback must be >1x; held-R2 fast-forward multiplies that configured base speed. Requires runtime/native investigation and installed-game timing verification.
- #414 — player-controlled minimap. Tap map button opens the map; hold toggles minimap state, overriding automatic combat/location visibility changes. Requires runtime/input/UI investigation and installed-game state-transition verification.
- #415 — editable item prices. **Core semantic-editor priority:** expose authoritative buy/sell price data with readable installed-game item names rather than leaving it as raw DataObject fields.
- #416 — editable enemy drops and drop chances. **Core semantic-editor priority:** expose authoritative enemy loot item/chance/quantity fields with readable enemy/item names, keeping ordinary drops distinct from steal/reward tables unless the game data proves they are shared.

## Evidence / next work

FF7R-specific CI covers Python syntax, plugin descriptor validation, gameplay/text parser tests and managed-service smoke on Windows and Linux. The next core-editor work is locating the authoritative FF7R item-price and enemy-loot DataObject schemas for #415/#416 and mapping them to semantic controls.

Live game acceptance remains separate: actual installed PAK indexing, representative real DataObject/text parsing, semantic price/drop effects, game load and deployed-value effects must be checked on an installed copy before #406 or its follow-ups are considered complete.
