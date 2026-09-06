# GitHub #37 — Premium Pack Rework

## Live request readback

The live issue and its latest owner comment were read before this repair. Merely
obtaining Premium Cigarettes was required to stop granting a card. Consuming an
actual Premium Cigarette was required to roll for a card not currently owned;
duplicates became eligible only after all 144 were owned. The latest comment
also required the percentage to be configurable because an unlogged 20 percent
miss was indistinguishable from a broken implementation. Loose world cards and
existing cards had to remain untouched.

## Authoritative evidence

- `datasets/vanilla/catalog_sp.ymt`, item
  `CONSUMABLE_CIGARETTE_BOX`, defined the purchasable record as a consumable
  tobacco provision. Its catalog transaction quantity was ten; it was not a
  separate non-consumable container record.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/generic_smoking_item.c`,
  `__EntryFunction__`, applied one smoking item's effects on
  `ENTITY::HAS_ANIM_EVENT_FIRED(Global_35, 442509369)`. That event was the
  concrete consumed-cigarette boundary.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/main.c`, the inventory
  acquisition switch at the `CONSUMABLE_CIGARETTE_BOX` case, separately showed
  help item 485 and added a card through either `func_513()` or `func_514()`.
  This established that the vanilla acquisition grant and the smoking consume
  event were separate paths.
- The same decompiled inventory helpers normalized
  `CONSUMABLE_CIGARETTE_BOX_USED` to `CONSUMABLE_CIGARETTE_BOX`; the opened
  premium record was therefore included as a premium smoking interaction and
  was labelled `Opened Premium Cigarettes` in the editor rather than sharing
  the ambiguous ordinary-cigarette label.

## Repair written

`GameplayTweaks/modules/premium_cigarette_cards.cpp` replaced the old ambiguous
inventory-count-decrease roll with a rising edge of Rockstar's authored consume
event `442509369`, and accepted both the full and opened Premium Cigarettes
records. `ChancePercent` defaulted to 20, was clamped to 0–100, used 0.1 percent
editor steps, and hot-reloaded within two real seconds. A successful roll chose
from the currently unowned cards until all 144 were present; only then did it
select from the full collection.

The acquisition watcher retained the vanilla-card suppression behavior only
after the Premium Cigarettes inventory count rose. Ordinary loose-card
increases were accepted outside that bounded acquisition window. Grant and
suppression calls were followed by inventory count readbacks. The unified log
recorded each smoke roll, effective chance, selected card and readback, plus a
30-second heartbeat whose `lastSmoke` field distinguished `not-executed`,
`executed-miss`, `executed-granted`, and `executed-grant-failed`.

The issue-local editor changes were:

- `editor/settings_schema.json`: `Card Chance per Premium Cigarette`, 0–100,
  0.1 step, consume-only behavior, selection policy and hot-reload semantics.
- `editor/vanilla_localization.json`: the used premium record became
  `Opened Premium Cigarettes`; ordinary opened cigarettes kept their existing
  label.

## Integration handoff

The integration owner must perform these shared-file changes together:

1. Remove the old #37 globals beginning with `g_cardSets` through `g_cardRng`
   and the old `initializeCigaretteCards`, `nextCardRandom`,
   `grantSmokingCard`, and `updatePremiumCigaretteCards` block from
   `GameplayTweaks/script.cpp`.
2. Add `#include "modules/premium_cigarette_cards.cpp"` after `readF` is
   defined, alongside the other feature-module includes.
3. Call `updatePremiumCigaretteCards(ped, now)`, which dispatches to
   `PremiumCigaretteCards::update`, every frame while the player ped is live and
   post-office mail protection is inactive. Leave
   `DuplicateCigaretteCards::update` on its existing 100 ms cadence. The new
   module internally rate-limits inventory polling to 100 ms; its public update
   must be per-frame so the authored animation event is not missed.
4. Add this exact default to `GameplayTweaks/GameplayTweaks.ini`:

   ```ini
   ; Percent chance that consuming one Premium Cigarette grants a card.
   ; Buying, collecting or discarding Premium Cigarettes never rolls.
   ; Hot-reloads within two real seconds; 0 disables grants, 100 guarantees one.
   [PremiumCigaretteCards]
   ChancePercent=20
   ```

No build, installation, release-manifest edit or GitHub label transition was
performed in this feature pass.

## Runtime acceptance boundary

Static verification could establish the exact authored event, configuration
contract, card-selection policy, readbacks and diagnostics. It could not prove
the player-visible game result. After the integration build is installed and
hash-verified, Lexer still needs to verify buying/collecting/discarding Premium
Cigarettes never retains the vanilla acquisition card; smoking full and opened
Premium Cigarettes produces logged rolls at configured 0 and 100 percent;
successful rolls prefer unowned cards until 144; loose cards remain collectible;
and stranger-mission/set turn-in recognition is unchanged. The issue must stay
in `test me` until those in-game checks pass.

## Static checks

- `python tools/reverse-engineering/verify_premium_cigarette_cards_issue_37.py`
- `python -m json.tool editor/settings_schema.json`
- `python -m json.tool editor/vanilla_localization.json`
