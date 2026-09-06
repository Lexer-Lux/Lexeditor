# GitHub #88 - reusable canteen

## Implemented in the isolated feature handoff

- Added `GameplayTweaks/modules/reusable_canteen.cpp` as an unregistered module.
- Kept `LEX_WATER_BOTTLE` as the inventory shell and its authored catalog
  interaction as the drink animation. A confirmed inventory decrement consumes
  exactly one separately tracked charge, then the module re-adds the shell if
  the native interaction removed the last copy.
- Capacity is five drinks. The item feed reports `N/5` after acquisition, use,
  and refill. At zero charges, using the item still permits its authored drink
  animation but restores the pre-interaction Stamina Core value and reports
  that the canteen is empty.
- `[CanteenDeveloper] StaminaCorePerDrink=25` is read from the main INI every
  two seconds and clamped to 0..100. The exact target is the core value captured
  at interaction start plus the configured amount, capped at 100. The caller
  supplies `&managedCore[1]` so CoreClock cannot discard a valid one-point
  configured restoration.
- Charges persist in `GameplayTweaks.canteen.ini`. The module does not grant a
  canteen merely because that file exists. Existing owners migrate full only
  when the state file is first created; later 0 -> 1 acquisitions initialize
  full.
- Exposed `refillReusableCanteen()` for #89. It fills an owned canteen to five
  without changing any core. `reusableCanteenStaminaCorePerDrink()` exposes the
  same hot-reloaded amount for direct pump drinking.
- Added `GameplayTweaks/canteen_recipe.fragment.tsv`, an issue-owned row for the
  unified custom crafting table. It preserves the previous acquisition cost of
  one `PROVISION_EMPTY_BOTTLE` rather than inventing a different recipe.

## Integration ownership

The integration agent must:

1. Include `modules/reusable_canteen.cpp` after `modules/world_economy.cpp`.
2. In `ScriptMain`, call
   `updateReusableCanteen(ped, now, dead || locked || postOfficeMailProtected,
   &managedCore[1]);` once per frame before the CoreClock reconciliation block.
3. Add this developer-only block to the shipped INI:

   ```ini
   [CanteenDeveloper]
   StaminaCorePerDrink=25
   ```

4. Merge the single row from `canteen_recipe.fragment.tsv` into
   `custom_crafting_recipes.tsv`, after reconciling with #22's ownership of that
   shared table.
5. In the already-modified shared `MyOverhaul/catalog_sp.ymt`, change both
   `LEX_WATER_BOTTLE` multiplicity quantities from five to one. Charges are
   state, not duplicate disposable items. Preserve its proven vanilla
   `CONSUMABLE_WHISKEY_USED` icon and interaction data; remove the record's
   fixed `0x696243AD` Stamina Core effect so the ASI is the sole restoration
   owner (ordering evidence below).
6. Change the existing localization to `Reusable Canteen` and describe the
   five-drink capacity. Do not claim a custom canteen model until its held-prop
   interaction has been proven in-game.
7. Build, install, hash-verify, and run the acceptance checks from the live
   issue. This feature agent did not compile or install the shared ASI.

## Deliberate runtime boundary

- Charge persistence is installation-wide because no proven Story Mode save-slot
  identifier is available to the ASI. Ownership is still determined from the
  active save's inventory, so the module never grants a canteen into another
  save based only on the state file. Separate saves that both own a canteen will
  share the last saved charge count until a per-save identifier is proven.
- The existing vanilla `CONSUMABLE_WHISKEY_USED` icon remains in use. The prior
  custom bottle icon was explicitly rejected and removed. Although vanilla
  `p_canteen01x` world props exist, no proven catalog interaction/PropData pair
  was found, so this handoff does not risk a missing held prop or broken use
  animation merely to rename the visual.
- Integration removed only effect `0x696243AD` from the `LEX_WATER_BOTTLE`
  record, leaving the global effect definition intact. Decompiled
  `generic_alcohol_item` ordering proves that fixed +25 effect applied at the
  final-swig event about 1.844 seconds before inventory removal; retaining it
  would visibly restore an empty canteen before the ASI corrected the core.
  The authored interaction and consumption still run with an empty effect list,
  and the module is now the sole owner of the exact configured restoration.
- Empty use is conveyed by the normal drink attempt followed by an item feed;
  it restores no core. Blocking the inventory action before its authored
  animation would require a different, proven inventory-app interception path.

## Static checks

- The feature files are isolated and do not edit `script.cpp`, the installer,
  generated knowledge indexes, GitHub labels, or another issue's worklog.
- The crafting fragment has the exact nine-column header consumed by
  `custom_crafting.cpp` and one valid ingredient/output row.

## 2026-08-06 acquisition-path correction

The installed implementation did not give Lexer a discoverable answer to
"where do I find the canteen." The recipe existed as the first custom crafting
row, but neither the issue update nor the normal HUD identified the station or
ingredient before ownership.

The issue-local canteen module now gives one delayed, once-per-session tutorial
when the active save does not own the item:

`Reusable Canteen: craft at any campfire with 1 Empty Bottle`

It deliberately does not repeat. A real 0 -> 1 acquisition now reports
`Canteen filled: 5/5 - refill at any water pump`, which makes both the capacity
and refill path visible at the moment the player obtains it. The empty feed
still identifies water pumps, and the existing pump interaction supplies the
visible refill prompt.

Re-added `GameplayTweaks/canteen_recipe.fragment.tsv` as the issue-owned source
row for integration reconciliation. It names the five-drink behavior, uses the
ordinary crafting station, costs one `PROVISION_EMPTY_BOTTLE`, and outputs one
`LEX_WATER_BOTTLE`. The already-integrated shared recipe table was not edited by
this feature pass.

Static checks confirmed the tutorial is gated by `owned`, delayed until the HUD
settles, and permanently latched after one display. No item is granted by the
tutorial. Runtime acceptance starts by entering any campfire crafting flow,
crafting the first `Reusable Canteen` recipe from one Empty Bottle, observing
5/5, then using any authored water pump after spending at least one charge.
