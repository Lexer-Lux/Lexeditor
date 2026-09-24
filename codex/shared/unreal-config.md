# Shared Unreal Engine config tool

Owner: `unreal_config.py` (root) plus `ui/unreal-config.js` (one shared
Engine Config panel). One editor, one panel, one CVar catalogue for every
Unreal game. Game modules supply locations, supported settings, exceptions,
and verification results. No per-game copy of the editor or the panel.

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
  override `LEXEDITOR_FF7R_ENGINE_INI`). Document-folder resolution follows
  the Windows shell Personal folder here too, so the legacy Graphics
  Tweaks path and the shared editor land on the same file when Documents
  is redirected. The Remake Tweaks page mounts the shared panel as an
  Engine Config card served by `plugins/ff7r/server.py`
  (`/api/unreal-config` status/apply/default/reset/refresh); the card
  renders even when the catalog yields no tweak groups, since Engine.ini
  editing needs no catalog entry. Status carries live `iniUnlocker`
  evidence (`verified`, `candidatePresent`) from the existing unlocker
  detector, rendered as an INI UNLOCKER row; `r.EyeAdaptationQuality`
  stays owned by the Graphics Tweaks group (markers shared and pinned by
  test) and renders read-only in the shared panel.
- Rebirth: Engine.ini location verified 2026-09-23 against an installed
  game (`Documents/My Games/FINAL FANTASY VII REBIRTH/Saved/Config/
  WindowsNoEditor/Engine.ini`, override `LEXEDITOR_FF7R2_ENGINE_INI`).
  Evidence: the user file exists at the candidate path, the install
  ships a template Engine.ini documenting the same path plus the
  `[ConsoleVariables]` mechanism, crash folders prove UE4, and
  GameUserSettings.ini proves the directory is game-managed.
  Per-setting effects are still unverified: every setting stays in the
  advanced view. Document-folder resolution follows the Windows shell
  Personal folder, so redirected Documents (e.g. `D:\Documents`) work.
  The Rebirth Tweaks page exposes an Engine Config subtab served by
  `plugins/ff7r2/server.py` (`/api/unreal-config` status/apply/default/
  reset/refresh) reusing this module; no per-game editor copy.

## Panel sections

Tweaks pages page cards into fixed-height columns and refuse a section
taller than one page, so the shared panel renders settings in small
groups of at most four fields (Display, Post-processing, Image quality,
Lighting and shadows, Distance and streaming). Catalogue keys missing
from the map fall into an Other settings section rather than vanishing.

## Rules the module enforces

- Managed block last in file; unrelated lines, comments, BOM, and per-line
  endings preserved.
- INI values report as overrides or observed file values, never as effective
  game values.
- Game default removes the override (inherit). Reset removes the block and
  restores journaled user values that vanished.
- Keys owned by a sibling tweaks group (Remake eye adaptation) cannot be
  applied or defaulted through this editor, render read-only in the panel,
  and survive reset-all.
- External edits and game rewrites block saving until status is reviewed
  (`refresh_snapshot`). Timestamped backups precede mutation.

## In-game acceptance steps (per game, manual)

Source tests and successful file writes are not in-game acceptance. For
each game, at a recorded game version, in representative gameplay:

1. Back up Engine.ini, open the Tweaks page (Remake: Tweaks tab;
   Rebirth: Tweaks tab, Engine Config subtab), and confirm the panel
   shows the real config path and no overrides.
2. Set one visual setting with an obvious effect (e.g. Motion blur 0,
   Chromatic aberration 0), save, and restart the game where noted.
3. Confirm the intended visual change in-game, then Use game default,
   restart, and confirm the stock look returns.
4. Confirm Reset all removes the Lexeditor block and restores any
   pre-existing user overrides from the journal.
5. Record the game version and the demonstrated settings; only then do
   they move to the normal view.

## Verification state

`tests/test_unreal_config.py` (24 tests),
`tests/test_ff7r_unreal_config.py` and `tests/test_ff7r2_unreal_config.py`
(service endpoints plus editor/server wiring),
`tests/test_unreal_config_ui.py` (one shared panel serves both pages),
`tests/unreal_config_browser_check.py` (rendered save round trip plus
small-window and 150% UI-scale readability on both Tweaks pages) and
`tests/verify_unreal_config.py` (13 checks, verifier sweep).
In-game effect acceptance for both games is open (issue 478).
