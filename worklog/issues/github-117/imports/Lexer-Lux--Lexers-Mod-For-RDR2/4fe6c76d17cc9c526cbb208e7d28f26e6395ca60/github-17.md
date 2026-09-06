# GitHub #17 — LEXEDITOR Settings Page Rework

## Implementation

- The old Settings tab rendered the INI section/key names directly, guessed
  booleans from a short key allowlist, showed no units, and appended every
  section as one full-width vertical table.
- Replaced that presentation with an explicit settings schema and a responsive
  multi-column card grid. MAP, MISC, and DEV are the first three cards.
- MAP contains every collectible-category switch, Train Markers, Auto Clear On
  Reach, and Auto Clear Distance. The redundant CollectibleMap global Enabled
  control is hidden.
- MISC contains Animal Density Multiplier, Hunter Hatchet Rework, Recoverable
  Unique Weapons, Mask Carrying Rework, Holstering Actually Holsters, and Sell
  Only Duplicate Cigarette Cards. AnimalDensity Enabled is hidden. The incoming
  Misc/TaggedOnlyOnMinimap setting from GitHub #94 is also registered here as a
  checkbox and appears automatically once it exists in the INI.
- DEV contains Campsite Key and Respawn Window.
- PartialBounty Enabled and MinimumPaymentCents are hidden from the editor.
  Their INI values were not changed.
- All settings not explicitly moved or hidden remain visible in their original
  INI section, now with human-readable labels. Numeric values render with a
  unit suffix; semantic booleans render as checkboxes. Technical section/key
  identities remain visible beneath labels for unambiguous troubleshooting.
- Decimal detection no longer misclassifies the hexadecimal campsite key as an
  HTML number input.

## Static verification

- Extracted the complete inline JavaScript and passed it to `node --check`.
- Exercised schema helpers in Node: group order, boolean recognition, unit
  lookup, acronym label splitting, and hidden partial-bounty controls passed.
- Parsed the current INI through `editor.server.get_gameplay_settings`: 232
  unique controls existed; exactly the four explicitly removed controls were
  hidden, leaving all other 228 represented by the generic-or-grouped render
  path.
- `git diff --check -- editor/editor.html worklog/issues/github-17.md` passed
  apart from Git's informational LF-to-CRLF warning.

## Integration handoff

- No visible browser was opened and no runtime files were edited.
- The integration agent should combine the incoming #94 INI change, run the
  editor API/static suite, rebuild generated knowledge indexes, and perform any
  visual/in-game acceptance handoff required before changing GitHub #17 state.

Integration added the #94 Misc key, removed the obsolete PartialBounty INI
section, and made partial repayment permanently enabled in the runtime instead
of merely hiding its controls. Inline JavaScript syntax and the settings API
passed; the current parser exposes 39 sections and 230 controls before the
editor's explicit grouping/hiding rules.

## Visible subsection correction

- The first card-grid version technically grouped settings, but each category
  was itself a small masonry card. That did not provide the visible page
  segmentation requested in the issue and matched the reported result that no
  subsections were apparent.
- Reworked every category into a full-width horizontal section with a prominent
  heading bar. Each section now lays its settings out in three columns, falling
  back to two and then one on narrower windows.
- Kept the technical `Section / Key` source below the human-readable name,
  including `... / Enabled`, per the follow-up decision. Help question marks
  remain inline with the setting name rather than occupying separate rows.
- Preserved the #124 parser behavior: repeated or differently-cased Misc
  sections still merge into one category and no contributed setting is lost.

## Subcategory rework, developer tagging, and a shared schema

Answering the follow-up comment on #17 point by point. Nothing below names a
key, default or range that was not resolved against `GameplayTweaks.ini` or the
code that reads it.

### The schema moved out of the HTML

`editor/settings_schema.json` (new) now holds the whole presentation layer:
category/subcategory layout, label overrides, supplemental help, the boolean
key list, the developer set, the hidden set and the dropdown choice lists.
`editor/server.py` reads it and attaches it to `/api/settings` as `schema`;
`editor/editor.html` renders from it. A missing or malformed schema degrades to
plain one-category-per-INI-section rendering rather than hiding anything.

This exists because the in-game menu (`GameplayTweaks/modules/settings_menu.cpp`,
not owned by this agent) currently reimplements the same label/unit/boolean
tables in C++. Both can read one file. That is also what makes "hide developer
settings when devmode is off" implementable in-game without a second list.

### Subcategories — the actual layout

`.settings-layout` is now `column-count:2`, so the page is **two columns of
categories**. Inside each category, `.settings-subs` is an auto-fit grid, so
each **subcategory is its own column** with its own header bar. Verified live in
a browser at 1600x1000: category left edges 18px and 802px (two columns);
Map's subcategory left edges 19/274/528px (three columns inside one category).
23 categories, 56 subcategories, 334 settings, no horizontal page scroll.

Layout as built (category: subcategories):

- Map: Minimap, Pause Map, Collectibles, Trains
- Stamina: Human Stamina, Horse Stamina, Wagon Team, Reserves
- Cores: Core Clock, Dead Eye, Tonics & Canteen, Toxicity, Temperature
- Tracers: Added Tracer, Vanilla Tracers
- Weapons & Ammunition: Shared Ammo Caps, Shared Item Caps, Radial Scrolling,
  Projectile Speed
- Spent Casings: Collection, Glow & Glint, Ejection Physics
- Movement: Combat Roll, Prone, Climbing
- Camera: View Locks, On Foot, Mounted & Vehicle, Aiming
- Binoculars: Access, Side Mask, Transition Probe
- Recon Tagging: Detection, Markers
- Wallet: Banking, Capacity by Gambler Rank
- Honor Prices: Behaviour, Multiplier by Honor Rank
- Horse: Needs
- Empty Bottles: Collection, Probe
- Bloodstain: Marker
- Campsites: Placement
- Bandit Masks: Behaviour, Mask Powers
- Belt Lantern: Light
- Radial Ammo Counts: Layout, Colours
- Fortified Overfill: Display, Geometry, Repaint Colours
- Wanted System Trace: Trace
- Compendium Probe: Probe
- Miscellaneous: Gameplay, Core XP, Horse Persistence

Requested moves, all done: collectible map merged into Map (there is no separate
Collectible Map category any more); Collectible Probe sits in Map/Collectibles
tagged DEV; Human and Horse Stamina are subsections of Stamina; Core XP Gain and
Horse Persistence are subsections of Miscellaneous; `[LostMoney]` is presented as
**Bloodstain**; tracer settings have their own Tracers category; Auto-Bank sits
with the wallet options under Wallet / Banking.

### Developer tagging replaces the DEV category

There is no DEV category any longer. Individual settings carry a `dev` flag,
render on a distinct background (`#2b2013`) with a DEV chip, and a toolbar
checkbox hides them. 23 settings are tagged; hiding them drops the page from
334 to 311 fields and removes the three categories that are entirely diagnostic.

The set is not a guess. Eight are gated by the runtime's own
`developmentModeActive()` (`GameplayTweaks/script.cpp:88`):
`HorseNeeds|DevelopmentTrace` (modules/horse_needs.cpp:89),
`CollectibleProbe|Enabled` (script.cpp:1188), `Prone|DevelopmentTrace`
(script.cpp:1216), `BottleProbe|Enabled` (script.cpp:1284),
`Climbing|DevelopmentTrace` (script.cpp:1361), `SpentCasings|DebugMarker`
(script.cpp:1447), `CombatRoll|DevelopmentTrace` (script.cpp:1453), and
`CollectibleMap|DeveloperMoveMaxDistance`, whose only consumer is the dev-gated
F2 relocate at script.cpp:2620-2626. `Campsites|Key` and
`Campsites|RespawnWindowMs` join them because the placement keypress sits inside
`#if GAMEPLAYTWEAKS_DEV_MODE` and is ANDed with `developmentModeActive()`
(modules/world_economy.cpp:1194-1196) — campsite placement does not exist at all
in a release build. The remainder are declared diagnostics in the INI's own
comments: `HumanStamina|ShowMode` (line 42), `CoreClock|WriteMode` (153-154),
`Binoculars|ShowZoomReadout` (543) and the #84 `TransitionAnimRate` /
`TransitionAnimLayer` probe (530-534), `CompendiumGlintProbe|Enabled` (553-554),
`AlwaysHolster|Log` (788), `RadialAmmoCounts|HeartbeatMs` (689) and the four
`WantedSystem` trace keys (865-872).

### Booleans are now extracted, not guessed

The old code recognised booleans from a hand-written name allowlist plus prefix
heuristics. The list is now every key the runtime actually reads with `readB()`
or `GetPrivateProfileIntA(...) != 0`, swept from `GameplayTweaks/script.cpp` and
`GameplayTweaks/modules/*.cpp` — 86 checkboxes render. Two were verified
individually because they do not use those forms: `Misc|TaggedOnlyOnMinimap` is
read as a string and tested `strtol(value) != 0` (modules/recon.cpp:1069-1076),
and `ReconTagging|CoreBackground` / `CoreTrack` are the two independently
switchable backing layers documented at GameplayTweaks.ini:588-596. The checkbox
checked-state test mirrors the runtime's own `!= 0`, not `== "1"`.

`Misc|Auto-Bank` is a checkbox now: modules/world_economy.cpp:394 reads it as
`GetPrivateProfileIntA("Misc", "Auto-Bank", 1, ...) != 0`. It was never a number.

### Dropdowns

Five free-entry fields became dropdowns, each from a documented value set:

- `ProjectileVisibility|Mode` — off / luminous_streak / corona. script.cpp:1198-1202
  parses this string: "corona" is mode 2, "off" or "disabled" are mode 0, and
  anything else falls through to the luminous streak. The three names offered are
  the ones GameplayTweaks.ini:705-707 documents.
- `SpentCasings|PickupMode` — native / legacy (INI 774-780).
- `Prone|EntryStyle` (INI 316-318), `Prone|BinocularMode` (INI 367-374),
  `Camera|MountedThirdPersonLevel` (INI 828-830, clamped 0..2 at
  modules/gameplay_camera.cpp:68-71).

A current value the schema does not list is offered back as its own option, so a
dropdown can never silently rewrite a value.

### Every setting has a "?"

Help resolves in this order: the INI's own comment for that key, then the
schema's supplemental text, then a pattern for the repeated numeric families
(Gambler-rank dollars, honor-rank multipliers, per-stance camera offset /
distance / low-camera with the real clamps from modules/gameplay_camera.cpp:84-85,
RGBA colour channels, and `Enabled`), then the INI comment block for the whole
section. Measured in the live page: 0 of 334 fields render without a help marker.

### Hidden

Four controls are hidden, all with a stated reason in the schema:
`CollectibleMap|Enabled` and `AnimalDensity|Enabled` (redundant, as before), and
per this comment `LostMoney|MapIcon` and `LostMoney|PropModel`. Their INI values
are untouched.

### Comment preservation

`save_gameplay_settings` rewrites only lines it matches as `key=value` in the
target section; every other line is passed through verbatim. Verified on a
scratch copy of the real INI by saving four values across four sections,
including the hex `Campsites|Key` and the `+`-containing `Rank+0Multiplier`:
903 lines before and after, all **466 comment lines byte-identical**, CRLF line
endings preserved, and exactly the four intended value lines changed.

### Verification

- `node --check` on the extracted inline JavaScript: clean.
- Schema resolved against the live INI: every hidden, boolean, dev, choice,
  label and help key names a section/key that exists; zero settings unclaimed;
  334 placed + 4 hidden = 338 total.
- Driven live in a browser against a throwaway server on port 8791 (stopped
  afterwards; Lexer's own instance on 8765 was left running and untouched).

While verifying the save path, the four-value test propagated to the installed
`GameplayTweaks.ini` in the game folder, because `save_gameplay_settings` copies
to `GAME_ROOT` after writing. The installed file was compared against the repo
copy — the only differences were those four test values — and then restored from
the repo copy, byte-identical. The repo INI itself was never written.

## Left for Lexer

1. **Combat-roll stamina cost does not exist.** The requested "amount of stamina
   consumed when doing a combat roll" has no key: `[CombatRoll]` reads only
   `Enabled`, `AllowFirstPerson`, `DevelopmentTrace` and `CooldownMs`
   (script.cpp:1451-1455), and no stamina spend appears anywhere in the roll path
   in modules/movement.cpp. It cannot be surfaced until the runtime reads one,
   and GameplayTweaks/ is another agent's file. Needs a runtime change first.
2. **`[Prone] ForceAcquisitionFeed` is dead where it is written.** The runtime
   reads `ForceAcquisitionFeed` from `[EmptyBottles]` (script.cpp:1387), not from
   `[Prone]`, so GameplayTweaks.ini:378 has no effect. It is shown, DEV-tagged,
   with help saying exactly that, rather than being silently dropped. Moving the
   line is an INI edit and this agent does not hand-edit that file.
3. **The in-game settings menu still has its own copy of this schema.**
   `GameplayTweaks/modules/settings_menu.cpp:79-150` duplicates the label, unit
   and boolean tables and knows nothing about developer tagging, subcategories or
   dropdowns. `editor/settings_schema.json` is written to be read by it too; that
   port is a GameplayTweaks-side task.
4. **`[CanteenDeveloper]` is not a developer section.** Its only key,
   `StaminaCorePerDrink`, is an ordinary gameplay value (INI 90-93). It is shown
   under Cores / Tonics & Canteen and is not DEV-tagged. Renaming the section
   would be an INI change plus a runtime change.
5. **Restart LEXEDITOR.** The `schema` field is new in `server.py`, so a
   long-running editor process keeps serving `/api/settings` without it. The page
   degrades safely (one category per INI section, no subcategories, no DEV tags)
   rather than breaking, but the rework only appears after a restart.

## 2026-08-09 correction against Lexer's latest comment

The earlier report above did not finish the issue. The remaining player-facing
items were implemented and checked against the current runtime reads:

- `Map / Marker Toggles` now holds the collectible category checkboxes and
  `Train Markers` in the same subcategory. Auto-clear and developer marker tools
  have their own Map subcategories.
- Added `Unique Items Rework`, with separate Hunter Hatchet and Recoverable
  Unique Weapons subcategories. They are no longer mixed into Miscellaneous.
- Renamed the actual mailed-set gate to `Cigarette Card Sell Safety`; its help
  now explains that cards needed by an unmailed set are protected and later
  copies become sellable after mailing the set.
- Fixed the boolean registry omissions for Gang Hideouts, Auto-Bank, vanilla
  tracer-only mode, recon backing layers and all four recon isolation switches.
- Hid the obsolete global/per-feature logging switches from both settings UIs.
  This does not disable `GameplayTweaks.log`; unified diagnostics remain
  automatic.
- Made developer rows unmistakably purple with a DEV chip in LEXEDITOR. The
  in-game menu now hides developer values when developer mode is off and uses a
  purple row plus `DEV` prefix when it is on.
- Added the requested `[CombatRoll] StaminaCost=10.0`. The runtime reads it and
  charges the proven `_CHANGE_PED_STAMINA` native exactly once, after the
  authored replacement roll is issued; the trace records before/after readback.
- Updated the Radial Ammo Counts schema to the current `FontFace` / `FontSize`
  controls and removed the deleted TextScale/IconCentreY controls.

`tools/reverse-engineering/verify_mod_settings_issue_17.py` passes all of those
relationships, the inline JavaScript passes `node --check`, `editor/server.py`
compiles, and the development ASI builds. LEXEDITOR was restarted hidden on
port 8765 and `/api/settings` returned the new 24-category schema.

The new gameplay binary was deliberately **not installed** over the separately
installed recon-crash candidate while that runtime test is pending. Therefore
GitHub #17 correctly remains `actionable`; only the editor portion is live now.

## Installed handoff

The gameplay-side settings changes shipped in development ASI
`BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5`;
source and game-root hashes match. The matching INI and schema were installed,
and LEXEDITOR remains live on port 8765. #17 was manually changed from
`actionable` to `test me` and read back as open with only `test me`.

## Current actionable pass

The settings surface now matches the current runtime instead of carrying dead
controls: binocular EquipP3/P4/P5 and the inverse tracer switch were removed;
tracers use direct Enabled semantics; ammo caps are grouped by the overhaul's
.225/.307/.444/shotgun/arrow pools; carried-mask item is hidden; camera draw/
stow timings are developer-only. Map, stamina, cores, tracer, binocular, and
developer categories were regrouped. Subcategory fields are forced to one
column and numeric spinner chrome is hidden so nested labels and final digits
are not clipped. The editor server clamps schema-ranged numeric saves. Both #17
verifiers, JSON parsing, inline JavaScript syntax, and Python compilation pass.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match; INI and schema are current. Workflow after
install: `test me`.

## 2026-08-10 field-help correction

LEXEDITOR reused a section's full introductory comment block as the fallback
help for any setting without its own key comment. This put large, unrelated
text behind several field-level `?` controls. `settingHelp` no longer uses
section help for fields. Section text remains on the category heading. A field
without authored help now receives one short setting-specific fallback.

`DeadEye|ConsumptionPointsPerSecond` now has explicit help: it controls outer
Dead Eye bar points drained per real second while Dead Eye is active, and 0
keeps vanilla drain. Both #17 static verifiers, Python compilation, JSON
parsing, and `git diff --check` passed. GitHub #17 remains open with `test me`.

## 2026-08-10 numeric-width correction

The latest screenshot showed that hiding browser spinner chrome did not solve
the defect: decimal values were still clipped. Each requested subcategory can
be only 232 pixels wide in the three-column layout, and the settings row split
that narrow width again between the label and the value. A unit suffix could
therefore collapse the input to only a few digits.

Setting labels and controls now use one grid column, placing the value on its
own full-width row. Numeric/text/select inputs also explicitly permit flex
shrink with `min-width:0`; spinner chrome remains hidden. The #17 page verifier
now requires both width guarantees. No visible browser was opened, and no
GitHub label was changed in this issue-local pass.

## 2026-08-10 actionable pass: setting lifecycle tags

The live issue added a new lifecycle requirement after the prior installed
test: keep developer tags and distinguish every setting that the running game
cannot observe after a save. The classification was made from the readers, not
from section names or whether a field looked technical.

The audit covered all 352 settings currently exposed by LEXEDITOR:

- 312 are genuinely live and remain untagged. The main group is read by
  `loadConfig()`, which `reloadIfChanged()` invokes from the
  `GameplayTweaks.ini` file-mtime edge. The remaining live readers have their
  own bounded paths: Minimap, Human Movement, Horse Needs, horse Core Clock,
  canteen, Premium Cigarette Cards, Recon presentation, Radial Ammo Counts and
  Projectile Visibility poll every one or two seconds; Horse Persistence and
  Tonic Refill read at use/update time; Casing Ejection reads at each spawn.
  The two concurrently added recon tag-distance controls were included in the
  audit and use the existing two-second recon settings refresh.
- 31 Fortification fields are `CONST`: `loadSettings()` has a static `loaded`
  guard and reads the section exactly once. Their requirement is an ASI reload
  or game restart.
- the three visible Wanted System trace fields are `DEV+CONST`:
  `loadWantedSystemSettings()` is called only during ASI startup. They state
  the same ASI/game restart boundary without losing their developer tag.
- Child Vulnerability is `CONST`: the process-wide hooks are installed or
  skipped once during ASI startup.
- Recon `DistanceFont` is `CONST`: `reconTextFontFace()` caches the value on its
  first draw. It requires an ASI reload or game restart.
- Projectile Speed is `CONST` with its different real boundary: run
  `GameplayTweaks/ApplyProjectileSpeed.ps1`, install the rebuilt weapon data,
  then restart the game. The help explicitly distinguishes that data-owned
  projectile physics from the live ASI read that only changes custom tracer
  marker travel.
- Three exposed dead/reserved controls are `CONST` but do not falsely promise
  that a restart will activate them: Core Clock `WriteMode`, Prone
  `ForceAcquisitionFeed`, and Camera `DisableHorseCameraCentering`. Each says
  that no action applies it in the current build and identifies the actual
  reader where one exists. The first two retain `DEV`, so current coexistence
  totals five fields when combined with the Wanted System controls.

LEXEDITOR renders the existing `DEV` chip unchanged and adds an independent red
`CONST` chip. Both chips are emitted by the same field renderer and can appear
together. Every CONST boundary is appended to the setting's ordinary `?` help
as `Apply requirement:` and is also present on the CONST chip itself. The old
toolbar statement that all edits apply live was replaced with an accurate note:
untagged settings apply live, while CONST shows the required restart or rebuild
boundary.

Static verification passed:

- `python tools/reverse-engineering/verify_settings_lifecycle_issue_17.py`
  audited 352 exposed fields, 312 live/untagged fields, 40 CONST fields, the
  actual reader evidence, all exact boundaries, and five DEV+CONST fields.
- Both existing #17 verifiers passed.
- `editor/settings_schema.json` parsed with `python -m json.tool`.
- The `/api/settings` producer returned all 40 CONST lifecycle records.
- Extracted inline JavaScript passed `node --check -`.
- `editor/server.py` and all three #17 verifiers passed `py_compile`.

No INI, gameplay source, ASI build/install, release manifest, GitHub label, or
running editor process was changed in this issue-local pass. Runtime/editor
acceptance still needs a refresh of LEXEDITOR and visual confirmation that red
CONST and blue DEV tags remain distinct, coexist on the five audited fields,
and expose the full boundary text through each field's help.
## 2026-08-10 integration correction

- #146 added the hot-reloaded `CoreCostGuard|Enabled` field after the original lifecycle count was recorded. The current audit is 353 exposed settings: 313 live/untagged and 40 `CONST`.
- #105 removed its unsafe hook installer entirely. `ChildVulnerability|Enabled` is now a retained compatibility key with no runtime reader, so its red `CONST` boundary says that no action applies in the current build instead of promising a restart.
- `verify_settings_lifecycle_issue_17.py` was updated to prove the new bounded reader and the zero-reader child compatibility key.
## 2026-08-10 combined release

- Release ASI built successfully: `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`.
- RDR2 was running, so one hidden payload-only installer was queued. The issue remained actionable pending game-root hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.

## `fuckups.txt` recurrence audit for the returned CONST styling

- **Primary visible evidence:** the latest 1659x240 issue screenshot shows DEV
  settings tinted across the complete field row, while CONST settings receive
  only a small red chip. The complaint is a real visual inconsistency; the
  lifecycle schema counts and API payload do not prove the requested styling.
- **Sanctioned path:** retain the existing `settings-field` renderer and its
  independent DEV/CONST metadata. CONST must become a row-level state just as
  DEV already is; DEV+CONST fields must visibly preserve both states rather
  than dropping one tag or relying on a tiny chip alone.
- **Execution proof:** exercise the real `/api/settings` producer and current
  `editor.html`, then inspect computed row styles and retain wide/narrow
  headless Chrome screenshots. Syntax/schema assertions alone are insufficient.
- **Rendered acceptance:** ordinary live rows remain neutral, DEV rows remain
  purple across the row, CONST rows are red across the row, and the five
  DEV+CONST rows visibly combine both treatments and both chips. Labels,
  controls and final numeric digits must remain readable at both widths.
- **Per-frame mutation:** this is editor presentation only. It must not add a
  gameplay poll, write, or frame mutation.

## 2026-08-10 full-row lifecycle styling and rendered acceptance

- CONST is now a row-level presentation state, not only a chip. CONST-only rows
  use a full red tint and red edge; DEV-only rows retain the established purple
  treatment; DEV+CONST rows use a full-width purple/red split with both edge
  colors and both chips. Ordinary hot-reloadable rows remain neutral.
- The lifecycle audit was refreshed for the concurrently added
  `Pocketwatch|TextSize` control. `pocketwatch_time.cpp::loadSettings(now)`
  re-reads it on a bounded two-second cadence, so it is live and correctly
  untagged. Current totals are 354 visible settings: 314 live/untagged and 40
  CONST, with five DEV+CONST fields.
- `verify_mod_settings_issue_17.py`, `verify_settings_page_issue_17.py`, and
  `verify_settings_lifecycle_issue_17.py` pass. The lifecycle verifier now also
  proves the full-row CONST and mixed-state CSS plus the Pocket Watch reader.
- `render_settings_issues_17_18.py` launched the real server/page in headless
  Chrome. DOM/computed-style readback found 354 rows, 18 visible DEV chips, 40
  CONST chips, five mixed rows, correct neutral/purple/red/split backgrounds,
  complete `Apply requirement:` help, no `undefined`, and no narrow page
  overflow or numeric-input clipping (minimum rendered numeric width 283 px).
- Rendered evidence:
  `worklog/issues/rendered/github-17-settings-wide.png` and
  `worklog/issues/rendered/github-17-settings-narrow.png`. Both were visually
  inspected; the full-row lifecycle colors and final numeric digits remain
  visible.
- This changes editor presentation only and adds no gameplay cadence or write.
  No build, install, or GitHub label change was performed.

## Recurrence audit — returned lifecycle colors and category placement

- **Primary visual evidence:** the latest live screenshot shows DEV rows tinted
  purple across their full width while CONST-only rows are red. The owner now
  specifies the actual color model: DEV is blue, CONST is red, and only a row
  carrying both states is purple because it combines blue and red. The latest
  comment also explicitly places Child Vulnerability under Miscellaneous.
- **Sanctioned path:** keep the one shared setting-row renderer and lifecycle
  classes. Change the DEV-only full-row treatment to blue, retain CONST-only
  red, and use a visually purple mixed treatment while preserving both chips.
  Move only the schema category/subcategory metadata for the compatibility
  Child Vulnerability setting; do not create a duplicate or alter its dead-key
  lifecycle boundary.
- **Execution proof:** render the real Settings route at wide and narrow widths,
  inspect computed backgrounds for neutral/DEV/CONST/mixed rows, and locate
  Child Vulnerability by its visible category. Schema/API presence is not UI
  proof.
- **Rendered acceptance:** DEV-only rows are visibly blue end to end,
  CONST-only rows are red, DEV+CONST rows are purple and retain both chips,
  Child Vulnerability appears under Miscellaneous, and final numeric digits
  remain readable with no page overflow at both widths.
- **Per-frame mutation:** editor/schema presentation only; no gameplay reader,
  write cadence, or frame mutation changes.

## 2026-08-10 corrected lifecycle colors and rendered acceptance

- The earlier purple DEV-only treatment was wrong. DEV-only rows are now blue,
  CONST-only rows remain red, and only DEV+CONST rows are purple. Both chips
  remain visible on mixed rows, and ordinary live rows remain neutral.
- `ChildVulnerability|Enabled` is now explicitly grouped under
  `Miscellaneous` / `Gameplay` in the shared schema. Its compatibility-key
  lifecycle boundary was not changed.
- The regenerated in-game settings schema contains 359 visible settings from
  371 total records. The editor and in-game settings menu continue to consume
  the same generated ordering and category metadata.
- `render_settings_issues_17_18.py` exercised the real page at wide and narrow
  widths. Computed-style readback proved blue DEV (`rgb(23,43,70)`), red CONST
  (`rgb(54,25,27)`), solid purple mixed (`rgb(43,32,62)`), neutral ordinary
  rows, 18 DEV chips, 40 CONST chips, five mixed rows, and
  `Child Vulnerability` under `Miscellaneous`. There was no page overflow or
  clipped numeric input at narrow width.
- Fresh rendered evidence is retained at
  `worklog/issues/rendered/github-17-settings-wide.png` and
  `worklog/issues/rendered/github-17-settings-narrow.png`.
- The pending #71 configuration fragment is now included by the shared schema
  generator: `HumanMovement|RoadSpeedMultiplier` appears under Human Movement
  and `HorseStamina|RoadSpeedMultiplier` under Horse Stamina. Both surfaces
  visibly expose neutral `1.0` defaults, bounds `0.10..1.15`, step `0.01`, and
  exact two-second hot-reload help. The rendered fixture composes the fragment
  without changing the shared main INI, and the static audit proves the shared
  main INI still has `HumanMovement|Enabled=0`.
- This pass changed editor/schema presentation only. It did not build, install,
  change GitHub state, or add any gameplay mutation.

## Integration reconciliation after roll-setting removal

- Removed the obsolete `CombatRoll|AllowFirstPerson` and
  `CombatRoll|CooldownMs` rows with their real INI/readers; they are not hidden
  compatibility settings.
- Re-audited 364 exposed settings: 324 hot-reloadable and untagged, 40 CONST,
  with five DEV+CONST rows. Added the already-hot Thermometer position readers
  to the lifecycle audit.
- The schema generator now lets the real main INI override pending fragments.
  This preserves Lexer's current `HumanMovement|Enabled=1` and road-speed
  tuning instead of replacing them with an old fragment default.
