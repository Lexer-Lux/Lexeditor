# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356292019 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/134

Created: 2026-08-06T02:12:28Z; updated: 2026-09-05T06:56:42Z

Exact metadata: [source record](sources/issue-5356292019-b4ec2ce042d75bc1c2ef7ce21e807c197af9215eb27a005e951d1ae312024c72.json).

HORSE FEED-BOND: FIND THE REAL DATA SOURCE — I can't find any bond tag on
     the sugar cube, so feed-bond isn't a simple catalog tag. Find where the game
     actually decides "this can be fed to a horse and grants N bond". Bonding is
     ranks 0-4 with data-defined thresholds, not one universal percentage scale.
     GOAL: expose it in LEXEDITOR so feed-bond can be added to ANY item with a
     chosen value — data-driven, not a scripted watcher.

## issue 5356292019 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/134

Created: 2026-08-06T02:12:28Z; updated: 2026-09-06T13:31:12Z

Exact metadata: [source record](sources/issue-5356292019-895efe40d6a4adca505354c73216166827987f14c75a1972b0732011d9b605da.json).

Allow chosen items to feed horses and grant a configured bond amount.

**Actionable — runtime mapping remains.** Native feeding uses a scripted allowlist and shared bond award, not a catalog bond field. A configurable mapping must integrate with actual feeding; the rejected after-consumption watcher must not return or double-award bonding. No new permission is needed merely to investigate that non-watcher approach.

## comment 5550118839 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/134#issuecomment-5550118839

Created: 2026-08-06T03:58:32Z; updated: 2026-08-06T03:58:32Z

Exact metadata: [source record](sources/comment-5550118839-e42b800374fdeab5693ed7255bd31fb2786e649031504b5a0f7cb8caadd462c8.json).

Research result: feeding already grants horse bond natively; the old sugar-cube watcher was removed because it double-counted that grant. Bond itself is `PA_BONDING` (attribute index 7) with ranks 0–4 and data/model-defined point thresholds. What remains unresolved is the feed-item-to-bond-value dispatch: no simple catalog tag on sugar cubes explains “feedable and grants N points,” so adding arbitrary items cannot honestly be exposed yet. The next static target is the Story feed interaction/consumable path and its item hashes; if the amount is engine-owned, a small read-only runtime trace should log inventory delta, horse bonding points before/after, and the consumed item. Do not restore a watcher as the feature—it would duplicate native awards again.

## comment 5550118864 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/134#issuecomment-5550118864

Created: 2026-08-06T07:44:31Z; updated: 2026-08-06T07:44:31Z

Exact metadata: [source record](sources/comment-5550118864-3ea45b02e21abecfdb9b9129d5b2e12941bb10bb9340257cfd0a6938f41b50dc.json).

Static research found the real split: horse feed eligibility is scripted; restorative effects are item-database-driven; the bond award is not a per-item catalog field.

**Concrete evidence**
- `player_horse.c::func_724` is a hard-coded switch allowlist of horse-feed item hashes, including hay cubes, oat cakes, fruit, herbs, peppermint, and `CONSUMABLE_SUGARCUBE`.
- `func_789` separately hard-codes the preferred feed ordering (11 ordinary feeds, then 26 herbs). Adding a catalog tag alone therefore cannot make an arbitrary item participate correctly in the vanilla interaction.
- Once an allowed item is consumed, `func_790` enumerates its Item Database effect IDs with `_ITEM_DATABASE_FILLOUT_ITEM_EFFECTS_IDS` and applies horse core/bar effects by effect type. This explains the data-driven nutrition/restoration portion.
- The bonding path uses horse state, not a sugar-cube tag. `func_960` reads horse bonding rank and `func_961` returns a fixed `20`; that fixed value is passed into the horse's bonding accumulator in the generic feed interaction. The sugar cube is only special-cased with common bulrush, English mace, and peppermint for a reaction/flag (`func_959`), not a unique bond-value field.
- The sugar-cube catalog entry contains ordinary consumable/provision tags and no bond-value member.

**Conclusion / viable implementation boundary**
LEXEDITOR cannot truthfully expose “bond value on any item” as a pure catalog-data edit. Supporting arbitrary feed items requires scripted/runtime changes to eligibility (and likely presentation/selection), plus an explicit per-item value table owned by the mod. That can still be configurable, but it would not be vanilla data-driven. Do not restore the old consumption watcher: feeding already reaches native bonding and a watcher would double-award.

**Human decision required**
Choose whether a scripted LEXEDITOR-backed mapping is acceptable despite the original “not a scripted watcher” constraint. If the requirement is strictly native catalog data only, static research says the requested generalization is not available.
