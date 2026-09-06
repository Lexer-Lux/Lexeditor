# GitHub #18 — In-game mod settings

## Implementation

- Added an isolated settings-menu module derived from the MIT-licensed RDR2
  Native Menu Base interaction model and Rockstar-style native drawing.
- F8 on keyboard or LB+RB on controller opens a section-grouped menu.
- The module parses `GameplayTweaks.ini` at open time, so every current setting
  and any future setting appears without a duplicated C++ registry.
- Human-readable names, units, semantic checkboxes, and help copied from the
  INI comments follow the schema rules already established by GitHub #17.
- Enter toggles a checkbox. Every other value has direct text/numeric entry
  through Rockstar's native on-screen keyboard. Left/right also provides a
  quick slider-like adjustment for numeric settings.
- Every accepted change is written through `WritePrivateProfileStringA`, so it
  persists across restarts. GameplayTweaks' existing two-second file watcher
  applies the edited values live.
- The menu reads the file again each time it opens, preventing stale values
  after LEXEDITOR or an external editor changes the INI.

## Integration handoff

1. Add `#include "modules/settings_menu.cpp"` to the integration-owned module
   include block in `GameplayTweaks/script.cpp`.
2. Call `updateInGameSettingsMenu();` once per frame near the start of the main
   gameplay loop, after `reloadIfChanged()`. The function disables frontend
   controls while open and returns true while it owns input.
3. Build the combined ASI, install it with the current INI, and verify both
   keyboard and controller navigation in Story Mode.
4. Acceptance: every INI section/key appears; checkbox writes 0/1; typed numeric
   and string values persist; left/right adjusts numeric values; the existing
   hot reload picks up a changed value within about two seconds.

## Static verification

- The runtime parser is intentionally generic; it does not filter hidden
  LEXEDITOR-only keys because issue #18 explicitly requires every INI setting.
- No integration-owned dispatcher, INI, generated index, build, install, GitHub
  state, or unrelated issue work was changed by this feature agent.

## Vanilla-style renderer correction

- The first installed menu's functionality worked, but its custom dark
  rectangles and plain text did not satisfy the requested RDR2-style
  presentation. Calling that implementation "derived from Native Menu Base"
  obscured the important fact that it had not actually ported the library's
  renderer.
- Replaced that presentation layer with a focused port of Halen84's
  MIT-licensed Native Menu Base drawing approach: the native `inkroller_1a`
  background, `menu_header_1a` header, `menu_bar` footer, split scrollers,
  animated-style red crafting highlight frame, real `tick_box`/`tick`
  checkboxes, and Rockstar `$title`/`$body` fonts.
- Preserved the already-working dynamic INI discovery, section navigation,
  numeric/text editing, persistent writes, controller input, and F8 access.
- Added `verify_settings_menu_issue_18.py`; it checked the vanilla sprite/font
  contracts, rejected a fallback rectangle renderer, confirmed attribution,
  and counted the current INI rather than retaining the stale original count.
- This correction remained local and uninstalled. In-game acceptance still
  requires verifying the sprite layout at the user's resolution, scrolling a
  long section, toggling a checkbox, changing a numeric value, and confirming
  that the edit persists and hot-reloads.

## 2026-08-10 returned layout correction

The installed vanilla-style renderer exposed three presentation defects. The
right-aligned column converted the target X coordinate into its complement,
placing section counts and values far outside their rows. Body text used an
arbitrary `centerY - 0.016` top coordinate and undersized fonts. The header text
also used a top-biased Y position and the wrong title.

The right margin now uses `x * 1920`, row text is centered from its 25 px
height, section/option/value fonts are larger, and the header is centered and
reads `LEXER'S MOD SETTINGS`. Static verification covers all four corrections;
combined build/install and in-game confirmation remain pending.

Combined release build succeeded with queued ASI SHA-256
`1EF0C29A5DD946673827ECDDEA1B5C6800BD148B5F2E3111256A5446CBA2707A`.
RDR2 was running, so installation remained pending.

Rebuilt with the #5/#128 integration as ASI SHA-256
`AEAE1D1D1C53861A6F507815030957D333E77D097E9F2E7F899EF5B2FF82B2A3`;
installation remained pending while RDR2 was running.

## `fuckups.txt` recurrence audit for the returned in-game menu

- **Primary visible evidence:** the latest returned test says values still float
  far outside their rows, the left-side menu is obscured by the cores/minimap,
  and its categories/order differ from LEXEDITOR. The earlier 1255x472 issue
  screenshot is the visual baseline for the first two layout defects.
- **Sanctioned path:** the in-game menu must consume the same checked-in
  `editor/settings_schema.json` category/subcategory/label/unit/lifecycle model
  as LEXEDITOR rather than rediscovering raw INI sections into a second UI
  taxonomy. Rendering must stay inside a right-side safe-area panel, with value
  X positions bounded to that panel and category/setting ordering alphabetical.
- **Execution proof:** static checks must prove schema-reader/writer parity for
  every exposed field, exact bounded draw coordinates, and the open-time read /
  accepted-change write paths. A build or draw-call existence is not visible
  acceptance.
- **Player-visible acceptance:** in Story Mode, open the menu at the user's
  resolution and verify it appears on the right above neither cores nor minimap,
  every count/value stays within its row, categories/subcategories match
  LEXEDITOR and are alphabetical, CONST boundaries are visible, and a boolean
  plus numeric edit persist and follow their documented live/restart boundary.
- **Per-frame mutation:** `updateInGameSettingsMenu()` may draw and suppress
  frontend controls once per frame only while open. INI parsing remains an
  open/refresh transition and INI writes remain accepted-edit transitions; no
  per-frame file I/O is sanctioned.

## 2026-08-10 returned-test repair

- The floating values had a concrete copied-renderer defect. The authoritative
  Native Menu Base implementation at
  `_downloads/NativeMenuBase/RDR2-Native-Menu-Base-master/src/NativeMenuBase/UI/Drawing.cpp`
  computes a right-aligned margin as `SCREEN_WIDTH - posX`. The current menu
  instead used `posX`, so the previous correction was backwards and could not
  fix the installed symptom. `settingsMenuDrawText` now uses the authoritative
  complement and retains Native Menu Base's `x=0` right-aligned draw origin.
- The panel moved from left center X `0.190` to right safe-area X `0.815`; every
  label, count, checkbox and value is derived from the panel's left/right
  bounds. It also uses Rockstar's proven top overlay draw order 7, while the
  right placement independently avoids the cores/minimap region.
- Removed the duplicated C++ hidden/developer/boolean/unit/label registries and
  raw-INI category taxonomy. The generated
  `settings_menu_schema.generated.h` is built from the same
  `editor/settings_schema.json` plus `GameplayTweaks.ini` that LEXEDITOR uses.
  It currently covers all 366 INI keys: 354 visible and 12 hidden, across the
  same 25 resolved categories and 62 category/subcategory pairs. Categories,
  subcategories and labels are alphabetized for the list menu. Choices,
  booleans, ranges, DEV, CONST, units, help and exact INI section/key owners are
  carried into the runtime model; unknown future keys still receive a neutral
  fallback until regeneration, while the verifier fails stale generated data.
- INI parsing remains an open transition. Accepted toggles/choices/typed or
  adjusted values alone call `WritePrivateProfileStringA`; generated ranges are
  clamped before persistence and `loadConfig()` is called after a successful
  write. The per-frame draw body performs no file read or write.
- `verify_settings_menu_issue_18.py` passes exact generated-header parity,
  unique coverage, alphabetical ordering, authoritative right-margin math,
  safe-area coordinates, draw order, schema-driven lifecycle and
  transition-bound reader/writer checks. The three #17 schema/editor verifiers
  also pass against the same 354-setting surface.
- No build/install or in-game visual claim was made. Required Story Mode
  acceptance remains: verify right-side placement and top layering at the user
  resolution; values/counts inside rows; matching alphabetical
  categories/subcategories; CONST/DEV styling; and one boolean plus numeric
  persistence test with their documented live/restart boundary.

## 2026-08-10 returned-test value-column inset

Lexer's latest visual result said the numbers on the right remained slightly
too far right. The existing renderer placed every right-aligned value at
`kTextRight=0.958`, only about 23 reference pixels inside the 0.970 panel edge.
This pass keeps the panel and label column fixed and introduces a dedicated
value/right-control column 0.018 normalized units (about 35 reference pixels)
farther left. Section counts, numeric/string values and checkboxes use the same
column so their alignment remains consistent. Footer pagination remains on the
outer text edge because it is not a row value.

The regenerated 365-visible-setting schema and exact #18 verifier passed. Installed in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`; visual right-column clearance remains `test me`.
