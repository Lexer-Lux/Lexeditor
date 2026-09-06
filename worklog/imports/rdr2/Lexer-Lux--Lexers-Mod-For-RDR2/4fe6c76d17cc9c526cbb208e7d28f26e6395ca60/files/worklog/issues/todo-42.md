# Worklog: Todo 42

## #42 carried mask permanently disabled — my own camp gate 2026-08-05

The regression is entirely the `inCamp` gate added last round in
`updateCarriedMask`: `const bool inCamp = SCRIPT_REFS(joaat("player_camp")) > 0;`
then `if (inCamp || busy) radialAvailable = false;` → `INVENTORY_DISABLE_ITEM`
every 500ms. `SCRIPT_REFS("player_camp") > 0` is NOT "the player is in camp".
`updateCampsites` (script.cpp ~2772-2781) calls `materializeCampsite` for the
nearest campsite within **120m** and player_camp then stays resident, so on any
save with campsites placed the gate is true across most of the map. Hence
"permanently disabled". Replaced with a distance test against
`g_campsites[g_materializedCamp].pos` < 15m.

NO LOG EVIDENCE EXISTED, and that was a second defect. The `carrier-sync` line
only prints on `lastDesiredProxy != desiredProxy || inventoryChanged`, so the
whole session after startup was silent: the installed log held exactly
`radialAvailable=1` at spawn and nothing more, while the segment was dark the
entire time. Added a transition log printing `radialAvailable` with `bit8`,
`inCamp`, `busy`, `materializedCamp` on every change. The bit-8 read
(`*getGlobalPtr(1935496 + 27) & 8`) is untouched and now separately visible, so
if the retest still greys out, the log names which of the three did it.

Built and installed 07:43. Untested in-game.

### retest: camp gate fixed, two defects left — both mine 2026-08-05 18:16

Camp half confirmed by the new transition log: `inCamp=1` appears twice, briefly,
with `materializedCamp=0`. Two remaining faults, both visible in the same log.

WORN SCAN NEVER MATCHED, AND THAT IS THE CHECK MARK BUG. The log shows
`wornRoute=-1` on every line of the session, and `525615296 proxy-redirect ...
worn=0` followed three seconds later by `525618734 proxy-redirect ... worn=0`
again — the second use, with the mask already on his face, still evaluated
`worn=false` and issued MASK_ON. `START_ITEM_INTERACTION` never received a
MASK_OFF from us, and `carrierWorn = scan || latch` therefore reduced to the
latch, which is why every latch patch failed to clear the mark. The scan compared
`Global_1946804.f_1497.f_1[slot*3]` against `joaat(routes[i].real)`. The address
is right (story `bandana.c` func_30 uses the same `1946804 + 1498 + slot*3`), the
COMPARISON is wrong: the applied component is the wardrobe record filling the
slot, not the catalog hash we request. func_30 compares nothing by hash — it
rejects `component == 0` and `component == Global_1946804.f_57[slot*11]` (the
outfit default) and then tests
`_ITEM_DATABASE_FILLOUT_ITEM_INFO(component).f_1 == category`. Reimplemented as
`itemCategory()` (native 0xFE90ABBCBFDC13B2, struct<2>, field 1, memoized) and
`maskOnFace` / `bandanaWorn` now come from category -525676072 / 81053684.
Exact-hash `wornRoute` is retained ONLY for wardrobe-selection identification,
where knowing which mask was previewed is the point.

Checked the MP set first and it is the wrong authority: `script_mp_rel/bandana.c`
uses Global_1952637 (`MPC_PLAYER_TYPE_*`), story uses Global_1946804. Offsets
differ (f_1675.f_1 / f_83[*12] vs f_1497.f_1 / f_57[*11]). Use script_rel.

MOUNT/VEHICLE GATE WAS NEVER VANILLA. `IS_PED_ON_MOUNT` and
`IS_PED_IN_ANY_VEHICLE` in the `busy` list produced `busy=1` from 525205968 to
525399562 — 194s of dead segment while riding. Removed both; dead/ragdoll/
swimming/scenario/interaction stay.

Built and installed 18:16. Untested in-game.

