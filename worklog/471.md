# #471 — Add a Formulae tab, starting with the Steal formula

## State (2026-09-23 impl/ff7r2-actionables pass)

- Read-only slice is done and stays read-only. BattleItemPossession rows
  and array elements decode via `/api/battle-item-possession`; the Data Map
  row `(#471)` is `partial` with target `formulae`. Every field is served
  with `editable: false` (`_source_only_payload`) and the payload states
  the Steal formula is not yet reconstructed.
- Proven storage schema is validated (`_BATTLE_ITEM_SCHEMA`:
  `NormalItemName/Percent_Array`, `RareItemName/Percent_Array`,
  `StealItemName/Quantity_Array`, `StealFaildCountArrayIndex`); public mod
  evidence says the 25% rate data is shared between steal/drop. The
  condition/arithmetic connecting `StealFailed` / `AlreadyStolen` /
  `NothingToSteal` / `StealSuccessRateAdd` is unproved, so no edit route
  and no Steal-only rate control exist.
- Verification this pass: 66 passed across the four ff7r2 test files;
  managed service smoke passed; plugin descriptor valid. No source changes.

## Blocker (needs installed game, Lexer)

- Complete Steal formula with every term named.
- Roll-vs-no-item failure branch conditions and the message hook, so the
  failure message can match the formula.
- Proof that array-element writes are accepted before any write path opens.

Stays `actionable`. A formula that is only read says so in the payload.
