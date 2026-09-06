# GitHub #148 — Thermometer

## Live acceptance read before implementation

The live issue was `actionable` on 2026-08-10 and had no comments. Its body
required a **Thermometer** item, maximum held **1**, purchasable at any general
store. Owning it must continuously show the in-game temperature at the
top-right, directly beneath the pocket-watch time position, styled like the
temperature text in the vanilla Alt location/info popup.

The attached GitHub user-attachment URL was no longer directly retrievable
outside the issue session (GitHub returned its not-found page). No asset name,
price, manual activation, setting, or alternate unit rule was inferred from it.

## Primary-source resolution

- `_downloads/natives.json` names `0xB98B78C3768AF6E0` as
  `_GET_TEMPERATURE_AT_COORDS(float x, float y, float z)` and
  `0xFF4AAF3275BAAB4F` as `_SHOULD_USE_METRIC_TEMPERATURE()`.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/aguasdulces.c`, `func_66`, is
  the exact vanilla Alt-popup path: read temperature at `Global_36`, query the
  player's metric-temperature preference, convert with `func_120` only for
  Fahrenheit, then `BUILTIN::ROUND` before formatting `TIME_AND_TEMP_C/F`.
  `func_120` is exactly `(C * 1.8) + 32`.
- `MyOverhaul/catalog_sp.ymt` proves `KIT_PLAYER_POCKETWATCH` is stocked and
  printed in `ST_GENERAL`, uses `S_INV_POCKETWATCH04X`, the existing
  `INVENTORY_ITEMS/KIT_PLAYER_POCKETWATCH` and
  `ITEM_TEXTURES/UI_KIT_PLAYER_POCKETWATCH` presentation, and a working
  `COST_SHOP_DEFAULT` purchase price.
- No thermometer model, texture, catalog record, or named game-data asset was
  found in the extracted Story data. The authored item therefore reuses the
  resolved watch presentation rather than shipping a guessed asset/hash. It
  explicitly omits `CI_TAG_POCKET_WATCH`, so it cannot trigger the vanilla
  hand-held watch interaction.

## Issue-owned implementation

- `GameplayTweaks/modules/thermometer.cpp`
  - ownership authority is `INVENTORY_ITEM_COUNT(joaat("LEX_THERMOMETER"))`;
  - inventory count, coordinate temperature and unit preference are sampled at
    1 Hz; the frame-scoped text draw is the only per-update native path;
  - matches Rockstar rounding and Celsius/Fahrenheit conversion;
  - draws a right-aligned `$body` readout (`N° C/F`) at top-right below the
    watch line, with the existing sanctioned `TEXTFORMAT/P/FONT` wrapper;
  - suppresses rendering across death/gameplay locks/protected UI while keeping
    bounded samples current;
  - logs ownership transitions and a 30-second idle/display heartbeat, so a
    missing item, suppressed draw, and active sample are distinguishable.
- `editor/thermometer_issue_148.py`
  - repeatably authors `LEX_THERMOMETER` from the proven watch record;
  - sets one `SLOTID_ANY` multiplicity, making max-held one independent of
    Arthur's actual pocket-watch inventory;
  - retains the existing proven purchase price because the issue supplies none;
  - strips sale value and the pocket-watch behavior tag;
  - adds both required shop surfaces: `ST_GENERAL` stock and catalogue page;
  - adds `LEX_THERMOMETER` / `_DESC` localization;
  - supports alternate catalog/string paths for non-destructive fixture tests
    and is idempotent.
- `tools/reverse-engineering/verify_thermometer_issue_148.py`
  - rejects native/decompiled-source drift;
  - verifies bounded sampling, ownership gating, suppression and HUD markup;
  - applies the editor to temporary copies of the real 16 MB catalog and string
    table, validates all item/shop/page/localization postconditions, then proves
    a second application makes zero changes.

## Static evidence

Passed:

```text
python editor/thermometer_issue_148.py --check
thermometer issue #148: item=1 stock=1 catalogue=1

python tools/reverse-engineering/verify_thermometer_issue_148.py
PASS: issue #148 thermometer runtime, catalog authoring, and source provenance

git diff --check -- GameplayTweaks/modules/thermometer.cpp editor/thermometer_issue_148.py tools/reverse-engineering/verify_thermometer_issue_148.py worklog/issues/github-148.md
```

No build, install, shared catalog mutation, shared dispatcher/config/manifest
edit, or GitHub label transition was performed in this feature pass.

## Integration requirements

1. Include `modules/thermometer.cpp` from integration-owned `script.cpp` after
   the core helpers and unified logger are defined.
2. In the main Story update, call:

   ```cpp
   Thermometer::update(ped, now, dead || locked || postOfficeMailProtected);
   ```

3. After all concurrent data work is merged, run once from the repository root:

   ```text
   python editor/thermometer_issue_148.py
   ```

   This is the sole step that mutates integration-owned
   `MyOverhaul/catalog_sp.ymt` and `MyOverhaul/strings.gxt2`.
4. Re-run the verifier, compile the combined ASI, install/hash-verify through the
   integration workflow, then restart the game (catalog data is startup-loaded).

## Remaining in-game acceptance

After buying Thermometer at two different general stores, confirm the store
blocks buying a second copy, the readout appears without equipping/holding an
item, its top-right vertical position is directly below the watch time line,
Alt's vanilla popup and this readout agree on rounded value and C/F unit, and
the readout disappears if the inventory item is removed. Static/build/install
evidence does not establish those player-visible results.
## 2026-08-10 installed release

- Included in release ASI `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
- Game-root ASI, catalog and localization hashes matched the integrated sources. The open issue moved from actionable to test me; purchase/capacity/display/unit behavior remains runtime acceptance.
## 2026-08-10 shared placement-control request

Lexer requested that #147's new X/Y positioning controls also apply to the
temperature readout. #148 therefore gains independent hot-reloaded X/Y
percentage settings; it does not inherit the clock coordinates or require the
pocketwatch to be owned.
## 2026-08-10 position correction

The thermometer used the same reversed Scaleform right-margin conversion as
the pocket-watch clock. PositionXPercent now represents screen position: 100
is the right edge, and lower values move the temperature left.
