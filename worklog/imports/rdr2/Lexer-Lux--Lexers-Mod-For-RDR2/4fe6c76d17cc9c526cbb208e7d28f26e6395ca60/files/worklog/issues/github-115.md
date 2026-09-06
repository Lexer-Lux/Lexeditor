# GitHub #115 - conditional newspaper map icons

## Evidence

- `shop_newspaper_boy.c` gates newspaper shopping in its `func_560` path by
  calling `func_564(0)`. When that returns zero, it displays tutorial/help item
  521: "You have already bought all currently available newspapers."
- `func_564` counts the first field of each of the 14
  `Global_40.f_9479[index]` records by state. State `0` is therefore the exact
  persisted predicate used by the vanilla shop for "can currently buy one".
- The six town scripts author newspaper-boy volumes at Annesburg, Blackwater,
  Rhodes, Saint Denis, Strawberry, and Valentine. Their volume centers are the
  coordinates used by the replacement markers.

## Implementation

- The always-visible `BLIP_AMBIENT_NEWSPAPER` data entry was made visually
  empty, including its zoom linkage fallbacks.
- `LEX_BLIP_NEWSPAPER_AVAILABLE` preserves the original vanilla newspaper
  texture and zoom linkages.
- `modules/newspaper_map.cpp` creates replacement markers at all six Rockstar
  vendor coordinates while any saved newspaper slot is in state `0`, and
  removes them within 500 ms when none is. It does not guess from chapter,
  missions, or inventory.

## Integration and acceptance

- The integration agent must include `modules/newspaper_map.cpp`, call
  `updateNewspaperVendorMarkers()` from the main loop, rebuild knowledge files,
  build, install both the ASI and `MyOverhaul/blipdata.ymt`, and hash-verify.
- In game, when at least one newspaper is currently purchasable, the map must
  show the vanilla newspaper symbol at all six newspaper vendors.
- Buy the last currently available newspaper. Within one second, all six
  newspaper symbols must disappear; approaching a vendor should produce
  vanilla's "already bought all currently available newspapers" response.
- Progress until a new newspaper unlocks. All six symbols must return without
  loading a different save, and the vendor must sell the new issue.

## Honest boundary

- Static evidence proves parity with Rockstar's purchase gate, but actual glyph
  visibility, zoom fallback behavior, and live transition timing require the
  requested in-game acceptance pass after integration and installation.

## Exact interaction-gate correction

The installed build left markers visible for Lexer at a vendor that offered no
newspaper interaction. Its correction still contained a stale-cache bug: once
`Global_1430252` had ever been initialized, the module trusted bucket zero
forever. Rockstar's `func_564` only considers that cache valid for 30 frames and
then reconstructs its three buckets from all 14 `Global_40.f_9479` records.

The module now mirrors that refresh before reading bucket zero, so the marker
gate uses the same current count as the exact vanilla interaction rejection
`func_564(0) == 0`, even after the shop script exits following a purchase. It
also records availability-count transitions in
`GameplayTweaks.newspaper-map.log`; a successful sold-out transition must say
`available=0 ... markers=removed`.

`verify_newspaper_map_issue_115.py` passed 11 module invariants and 5 direct
decompiled-script checks. This correction was static-only in the feature pass;
it was not built or installed there, and #115 remained actionable.

The verifier's original log assertion named the obsolete per-subsystem file.
Runtime state now goes through the unified logger as subsystem `newspaper`; the
verifier checks that actual call instead. This changes no gameplay behavior and
does not weaken the required `available=0 ... markers=removed` evidence.

## 2026-08-12 returned regression and repair

The #114 focused dispatcher trace proved this module broke every shop as soon
as it was enabled. It copied Rockstar's `func_564` cache refresh and wrote
`Global_1430252` plus its three buckets from GameplayTweaks' unrelated main
loop. Immediately afterward, healthy shop volume handles became invalid,
shop states cycled, and the LOCKED presentation bit appeared.

The marker updater now counts state-zero entries directly from the 14 persisted
newspaper records into a local variable. It never reads or writes Rockstar's
shared newspaper-shop cache. The verifier rejects every global write and any
future access to `Global_1430252`. #115 is not accepted until its conditional
markers and the restored shop interactions are both confirmed in game.
