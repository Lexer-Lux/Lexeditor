# GitHub #31 — Proper Alcohol Tags In Editor

## Authoritative source

The numeric strength is not a catalog tag or consumable-effect record. Story
Mode's `generic_alcohol_item.c`, `func_4`, hardcodes a switch on the interaction
item and returns the amount added to `Global_1935436.f_9` per authored swig. The
two saloon drinks run four swigs; every inventory drink runs one. The Wolf Heart
Trinket then halves that amount. `long_update.c` reads the same global for the
Sober/Drunk/Wasted state transitions at 0.50 and 0.75 and for the pass-out
sequence.

The complete imported base table is:

| Item | Vanilla strength |
|---|---:|
| `CONSUMABLE_SALOON_BEER` | 0.10 (4 × 0.025) |
| `CONSUMABLE_RUM_USED` | 0.10 |
| `CONSUMABLE_BRANDY_USED` | 0.10 |
| `CONSUMABLE_GIN_USED` | 0.10 |
| `CONSUMABLE_SALOON_WHISKEY` | 0.40 (4 × 0.10) |
| `CONSUMABLE_WHISKEY_USED` | 0.13 |
| `0xE0F2E219` | 0.13 |
| `CONSUMABLE_RUM` | 0.17 |
| `CONSUMABLE_BRANDY` | 0.17 |
| `CONSUMABLE_GIN` | 0.17 |
| `CONSUMABLE_WHISKEY` | 0.25 |
| `0x9BDEBF00` | 0.25 |
| `CONSUMABLE_MOONSHINE` | 0.30 |
| `CONSUMABLE_AGED_PIRATE_RUM` | 0.50 |

The two raw hashes are genuine catalog records used by the same switch. Their
models are `P_BOTTLEJD_USED01X` and `P_BOTTLEJD01X`; they carry the saloon
whiskey drink-class tag. They must be parsed as literal hashes, not passed to
JOAAT as the text `"0x..."`.

## Implementation

- Added `datasets/vanilla/alcohol_strengths.csv` as the complete imported
  Story-script baseline.
- Added `editor/alcohol_strengths.py`. It merges the baseline with the sparse
  GameplayTweaks override file for display, validates the real 0–1 domain, and
  writes only values that differ from vanilla. Resetting a value to its vanilla
  number therefore removes the runtime override.
- Kept the requested Moonshine customization as the sole override:
  `CONSUMABLE_MOONSHINE,1,0.3,1`. The last two columns record the vanilla
  per-drink baseline and authored swig count for the runtime adjustment.
- Added `tools/check_alcohol_strengths.py`, which independently parses the
  hardcoded switch and refuses any missing, extra, or changed imported value.

The existing Items UI and `/api/alcohol-strengths` response contract already
have the numeric field. No catalog edit is required. The current checkpoint's
single-row API made every other drink display zero, however, and its runtime
treated the configured number as an amount to add on top of Rockstar's amount.
That was not an actual per-item value and would make most edits too strong.

## Integrator-owned wiring

`editor/server.py` must delegate its existing `get_alcohol_strengths` and
`save_alcohol_strengths` functions to the same-named functions in
`editor/alcohol_strengths.py` (use a relative-import fallback so both
`python editor/server.py` and `import editor.server` work). The GET/POST routes
and response field `entries` do not change.

In `editor/editor.html`, retain all concurrent #17 work and make only these two
alcohol-input corrections:

- change `step:"0.05"` to `step:"any",max:"1"` so precise values are accepted
  and the documented 0–1 range is enforced by the control;
- change the help text from "0 has no runtime override" to "0 adds no
  drunkenness". Returning to vanilla is done by entering the displayed vanilla
  value; zero is a real override.

The integrator must correct the existing `script.cpp` alcohol watcher before
building. Required semantics:

1. Parse `0x########` keys with `strtoul(..., 16)`; JOAAT only symbolic keys.
2. Parse target, vanilla, and swig-count columns and treat target as the desired
   total per drink, not an extra additive dose.
3. Capture `Global_1935436.f_9` when the matching item interaction begins. On
   each proven consume animation event `442509369`, set the global after
   Rockstar's same-frame write to `clamp(level_before + target * completedSwigs
   / swigs, 0, 1)`. This covers saloon drinks, which have no inventory decrement,
   as well as one-swig inventory bottles. Keep the ped drunkenness natives
   synchronized for presentation.
4. At target 1, drive the game's real alcohol global to 1 so `long_update.c`
   owns the normal blackout/pass-out path. The current fallback only calls
   `TASK_KNOCKED_OUT`; that can knock Arthur down without proving the alcoholic
   pass-out/Guarma relocation behavior and is not sufficient acceptance.

This runtime change belongs in the integration-owned dispatcher/source. It was
not edited by the feature agent.

## Static verification

- `python tools/check_alcohol_strengths.py` passed: all 14 rows match
  `generic_alcohol_item.c func_4` exactly.
- `python -m py_compile editor/alcohol_strengths.py
  tools/check_alcohol_strengths.py` passed.
- An isolated temporary override test passed baseline merge, Moonshine 1 over
  vanilla 0.3, Gin 0.42 sparse save, and reset of Gin/Moonshine to vanilla.
- All 14 keys resolve to records in both vanilla and MyOverhaul catalogs; the
  two unresolved symbolic names are retained as their exact catalog hashes.
- `git diff --check` passed for the issue-owned files (Git only reported its
  informational LF-to-CRLF warning for the existing GameplayTweaks CSV).

## Runtime acceptance after integration/build/install

1. In Items, confirm every alcohol record shows its real numeric base value;
   Gin is 0.17, Moonshine shows the configured 1 with vanilla 0.30 available
   from the imported baseline, saloon beer is 0.10, and Drink class
   remains a separate coarse tag selector.
2. Change Gin to 0.42, save, reload LEXEDITOR, and confirm 0.42 persists while
   the CSV contains one sparse Gin override rather than rewriting catalog tags.
3. Consume Gin from sober and confirm the alcohol global rises by 0.42 total,
   not vanilla 0.17 plus another 0.42. Set Gin back to 0.17 and confirm its
   override row disappears and vanilla behavior returns.
4. Consume one Moonshine from sober. Confirm it reaches the game's Blackout
   state through the normal drunkenness/pass-out sequence, rather than merely
   playing a generic knocked-out task.
5. At the established Guarma exploit location, confirm the Moonshine blackout
   still triggers the intended relocation path despite the reduced carry cap.

## 2026-08-06 editor regression repair

Lexer's latest screenshot and comment are authoritative: the Items row showed
`Drunkenness 1` beside the ordinary drink-class selector, and he reported that
every drink's previously distinct numeric value had become 1. The API on disk
now returns the correct 14-value merged table, but the browser had been trusting
the flattened `entries` object. That made an older/poisoned response capable of
rendering the sole configured Moonshine override on every alcohol row; worse,
the next catalog save would send that flattened table back and persist it.

`editor/editor.html` now reconstructs each displayed value strictly from the
imported `vanilla` map plus the sparse `overrides` map and the current unsaved
edit. It no longer uses flattened `entries` as an input. Saving likewise sends a
fresh complete table built from those authoritative maps, so merely opening and
saving Items repairs an old browser session instead of writing all ones. Each
numeric input also shows its `V` reference value inline, making the intended
Moonshine override (`1`, vanilla `0.3`) visibly different from ordinary Gin
(`0.17`) and Beer (`0.1`).
