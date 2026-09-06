# GitHub #57 - sell cigarette-card duplicates after set turn-in

## Evidence

- Story Mode `shop_post_office.c::func_1751` handles successful card-set parcel
  transactions. It reads each parcel's authored bit (`51132409`) and ORs that
  bit into `Global_40.f_12019` before scheduling Phineas's reward.
- Rockstar's set-to-bit mapping is ACT=1, PAM=2, AML=4, ART=8, GRL=16, GUN=32,
  HOR=64, INV=128, LND=256, PLT=512, SPT=1024, VEH=2048.
- The earlier private `BundleSeen`/inventory-absence inference could not recover
  sets mailed before installation and did not prove that disappearance was a
  successful Phineas transaction.

## Implementation

- Added `modules/duplicate_cigarette_cards.cpp`. It reads the authoritative
  persistent Story mask and independently unlocks each of the twelve sets.
- Original `DOCUMENT_CIG_CARD_*` records remain unsellable. Once a set's bit is
  present, any originals from that set are migrated to its set-specific
  `LEX_DUPLICATE_CIG_CARD_*` resale record, including copies that predate this
  build. Submitted originals are never re-granted.
- Conversion grants one resale record before removing one original and rolls
  the grant back if removal fails, avoiding loss when a native or inventory cap
  rejects either side.
- Corrected `build_duplicate_cigarette_cards.py` to write an explicit fence
  `accept` override (the former `accepted=True` field was ignored by the API).
- `verify_duplicate_cigarette_cards_issue_57.py` checks the exact 12-bit map,
  recoverable conversion ordering, all 144 unsellable originals, all 12 resale
  records, and fence acceptance.

## Integration boundary

- The integration owner must include the new module, replace the old
  `g_cardSetMailed`/`BundleSeen` conversion branch with
  `DuplicateCigaretteCards::update(g_duplicateCardsEnabled)`, then perform the
  full build/install. Static verification does not establish in-game acceptance.
