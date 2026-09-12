# #162: Pickup sound routing and brass audio

[Live issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/162)

## Current requirements

Expose item-to-sound-category mappings and casing sound set/name controls. Use one brass event for native and custom casing pickup paths. The issue permits the editor work before the custom sound sample is supplied. The event and audio bank must exist before XML can use a new category.

## Implemented on 2026-09-08

- Added Loot Tables > Pickup sounds. A master list holds mapping identities; the detail pane uses a bounded select for the existing categories and sound sets.
- Edits use the global dirty count and save flow. Failed saves retain edits. Reference datasets are read-only.
- Added the current update_1.rpf loot_sounds.meta extraction entry. Inspected the installed 31,822-byte source: 522 mapping rows, 45 categories, two maps. Only this small file was extracted into the private game-data cache.
- Added a parser that keeps duplicate keys distinct by map, section and position. Changes preserve other XML text and reject unknown events. Saves write the selected mod file and register its LML replacement path.
- Existing SpentCasings PickupSoundName/PickupSoundSet settings remain the casing controls. No runtime or catalog changes were made.

## Evidence

- 32 backend tests and 17 subtests passed across pickup sounds, RDR2 issue repairs and inventory icons.
- Headless production UI fixture passed: select edit, global dirty count, failed-save retention, successful save/reload and disabled reference control. Render inspected at 1000 x 750; no overlap seen. Screenshot: out/loot-sounds/routing.png.
- Frontend syntax: 22/22 scripts passed. The new browser fixture is included in tools/verify_browser_regressions.py.

## Remaining scope

The new editor slice is checked with synthetic data and the installed XML schema. It is not evidence of in-game audio acceptance. The custom brass sample, source/credit details, audio-bank registration and shared native/custom brass event are still required. Do not mark the full issue complete or delivered from this editor patch alone.

## Integration review repair

- Saves now stage the data and manifest before replacing either live file. A manifest replacement failure restores the exact previous data, or removes the newly created file. A source change during staging stops the save.
- If rollback fails, the bounded staging folder remains in the mod directory with the original data and manifest. The error reports its path. Normal success and failure remove staging files.
- Injected data-write, routing-write, data-replacement, manifest-replacement and rollback failures cover both existing and absent target files (10 subtests).
- Help now gives a plain explanation and the Casing settings location. Added item/sound search and mapping count. A 522-row headless fixture selects the final row, filters it, saves it, clears the filter and checks list scrolling and page width. The final render was inspected.
- Updated checks: 33 backend tests and 27 subtests passed; headless pickup sound fixture passed; 22/22 frontend syntax checks passed. This remains editor evidence, not in-game sound acceptance.

## Recovery storage bound

A save now claims one fixed `.loot-sounds-recovery` directory with atomic directory creation. Existing recovery folders, including prior random-name folders, block another save before the source is read or a no-change result is returned. Recovery is never removed by a retry. The repeated-failure test retries three edits after rollback failure and confirms there is still exactly one folder and all first recovery bytes are unchanged. The 33 backend tests and 27 subtests pass after this change.

## Root integration check

Added an injected concurrent edit between the initial read and rollback staging. It failed before the repair: the later snapshot hid the source change and stale output replaced it. The save now compares that snapshot with the original bytes before any live replacement. Focused result: five tests and ten subtests pass. The prior full suite passed333 tests,149 subtests, with four skips; the new focused race test ran after that full result.
