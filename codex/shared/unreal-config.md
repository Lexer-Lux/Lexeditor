# Shared Unreal Engine config tool

Owner: `unreal_config.py` (root). One editor, one CVar catalogue for every
Unreal game. Game modules supply locations, supported settings, exceptions,
and verification results. No per-game copy of the editor.

## Catalogue

UE4 CVar set in `CATALOGUE`: eye adaptation, motion blur, depth of field,
bloom, chromatic aberration, sharpening, anti-aliasing, shadow resolution,
reflections, volumetric fog, draw distance, foliage density, texture
filtering, streaming budget, frame limit, VSync. Each entry has a
plain-language name, description with tradeoffs, type, range or choices,
dependencies, and restart requirement.

## Evidence tiers (per game, per setting)

- Defined by the engine: in the catalogue.
- Accepted by the game: value written through the managed block path.
- Demonstrated effect: seen working in the game at a recorded version.

Only demonstrated settings appear in a game's normal view. Accepted or
defined-only settings stay in the advanced view, marked, and out of presets.

## Games

- FF7R: Engine.ini path proven
  (`Documents/My Games/FINAL FANTASY VII REMAKE/Saved/Config/WindowsNoEditor/Engine.ini`,
  override `LEXEDITOR_FF7R_ENGINE_INI`). Writing needs a verified INI
  unlocker; `r.EyeAdaptationQuality` stays owned by the existing FF7R
  Graphics Tweaks group (markers shared and pinned by test).
- Rebirth: config location undiscovered. Candidate
  (`Documents/My Games/FINAL FANTASY VII REBIRTH/...`, override
  `LEXEDITOR_FF7R2_ENGINE_INI`) is unchecked against an installed game.
  Discovery probes; nothing is claimed until a file is observed.

## Rules the module enforces

- Managed block last in file; unrelated lines, comments, BOM, and per-line
  endings preserved.
- INI values report as overrides or observed file values, never as effective
  game values.
- Game default removes the override (inherit). Reset removes the block and
  restores journaled user values that vanished.
- External edits and game rewrites block saving until status is reviewed
  (`refresh_snapshot`). Timestamped backups precede mutation.

## Verification state

`tests/test_unreal_config.py` (19 tests) and
`tools/verify_unreal_config.py` (9 checks, verifier sweep). In-game effect
acceptance for both games is open (issue 478).
