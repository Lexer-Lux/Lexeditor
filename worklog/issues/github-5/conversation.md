# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5201356870 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/5

Created: 2026-08-20T08:29:33Z; updated: 2026-09-05T06:16:46Z

Exact metadata: [source record](sources/issue-5201356870-2bcc09fc36d0762aa7e08979f82be0855a06b2936a189162620e8e0c8f52457f.json).

Migrated from Lexer-Lux/rdr2-overhaul#200 because this is Lexeditor interface work.

The original picker request is already implemented: Item Effects and Tags use the shared full selectors and have no browser-native free-entry fields. The remaining request is a consistent reference display for fields that can contain an arbitrary number of entries.

Reference screenshots from the original issue:

![Current Items Effects and Tags reference display](https://github.com/user-attachments/assets/4bed2d8a-d9a9-403d-a3ac-45cb496a4245)

![Compact beside-value reference stack](https://github.com/user-attachments/assets/17fedf2f-e9cd-470e-b08c-36382e4fa0ff)

## Required design

- Use one shared multi-value reference component for Item Effects, Item Tags, and Challenge Rewards.
- The top segment contains the current editable entries.
- Each current entry has its compact reference stack to the right, like other beside-value references.
- For each reference dataset, show a green check when that exact entry and value match, a red X when the entry does not exist, and the reference value when the entry exists with a different editable value.
- A horizontal divider separates current entries from reference-only entries.
- The bottom segment contains entries that exist in one or more references but not in the current data. These ghost entries are muted or semitransparent but otherwise use the same entry and reference presentation.
- Existing add, remove, selector, duplicate-prevention, read-only, dirty-state, undo/redo, and save behavior remains unchanged.
- Do not extend this design to other multi-value fields without approval.

## Acceptance

- Adding or removing a live tag, effect, or reward updates its per-reference check, X, or value immediately.
- A field-level check cannot remain green when its live membership differs from a reference.
- Reference-only tags, effects, and rewards appear below the divider as non-editable ghost entries.
- The three fields use the same shared component and visual rules.
- Hidden rendered checks cover a matching entry, an absent entry, a different value, and a ghost entry without changing live editor data.


## issue 5201356870 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/5

Created: 2026-08-20T08:29:33Z; updated: 2026-09-06T13:32:24Z

Exact metadata: [source record](sources/issue-5201356870-cf81da9586b2029e56e8233e2f5458e77b7d17b2bea1b8ef740722aa5bf0070c.json).

**Needs testing.** Per-entry reference matches and separate reference-only rows are implemented.

Original examples: [1](https://github.com/user-attachments/assets/4bed2d8a-d9a9-403d-a3ac-45cb496a4245), [2](https://github.com/user-attachments/assets/17fedf2f-e9cd-470e-b08c-36382e4fa0ff).

- [ ] Restart Lexeditor. In a test RDR2 mod, add/remove an Item Effect or Tag. Reference marks should update; missing entries should appear below the divider. Undo the edit.
- [ ] Change a Challenge reward. Confirm the same layout works and Add stays below the list. Report a mismatched row or screenshot.

## comment 5353565761 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/5#issuecomment-5353565761

Created: 2026-08-20T08:46:57Z; updated: 2026-08-20T08:46:57Z

Exact metadata: [source record](sources/comment-5353565761-654a23fb6bfcecc4befc0ad70acb22cd7490fe0f9a4cf90f0d007835707a9e27.json).

Implemented the moved design.

Item Effects, Item Tags, and Challenge Rewards now use one shared reference-aware multi-value component. Current entries stay above the divider. Each entry shows a check when it matches a reference, an X when that reference does not contain it, or the reference value when the same entry has a different value. Reference-only entries appear below the divider as disabled, muted ghosts.

The full effect, tag, and reward selectors remain available. The old field-wide Tags check and array-position Challenge Reward comparison are gone.

The static contract, RDR2 plugin smoke test, and hidden rendered RDR2/Warband suite pass. The rendered fixture proved matching, absent, different-value, and reference-only cases without saving or changing live files.

Other possible candidates are carry-cap rules, recipe ingredients/unlocks, and loot or matrix yield lists. I left them unchanged pending approval.


## comment 5394002627 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/5#issuecomment-5394002627

Created: 2026-08-24T10:33:23Z; updated: 2026-08-24T10:33:23Z

Exact metadata: [source record](sources/comment-5394002627-62f9b8c1683e646ef44055b0d0e1d85fbdda054f530b1c13cc3ed57dc61909c8.json).

Fixed the colorless source badge in Item Tags. The shared multi-value component now uses the same green, bold Vanilla \V\ as the standard reference stack; the same shared rule also preserves the normal colors for K, 1899, UCO, and CT sources. The direct computed-style comparison and complete hidden RDR2/Warband render suite passed.

## comment 5462074961 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/5#issuecomment-5462074961

Created: 2026-08-29T11:23:44Z; updated: 2026-08-29T11:23:44Z

Exact metadata: [source record](sources/comment-5462074961-c4d53346eeceff1284ce826fbc4dcccd3eb0c514a1770b0914bd01fd16ed1f17.json).

The ugly chip-side source markers were not a size limitation. That component hard-coded Consolas, while the normal compact provenance stack uses the RDR2 body font. Both components now share the complete marker style: typeface, size, line height, source color, and weight. Effects, Tags, and Challenge Rewards now use the same-looking V/K/etc. markers as the standard reference stack.

## comment 5549836325 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/5#issuecomment-5549836325

Created: 2026-09-05T06:00:43Z; updated: 2026-09-05T06:00:43Z

Exact metadata: [source record](sources/comment-5549836325-c12f3d8f33132e4bb320ac28dea647130b0181e6452f9cb1fcdae6c5f5a4afef.json).

The Challenge Rewards add button now sits below the complete reward list, including reference-only entries. Hidden checks confirmed the position. A matching challenge counter no longer shows a Vanilla reference; changing it shows the reference, and restoring it hides it again.

## comment 5549917528 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/5#issuecomment-5549917528

Created: 2026-09-05T06:16:46Z; updated: 2026-09-05T06:16:46Z

Exact metadata: [source record](sources/comment-5549917528-5c8ef1aed43047583e63ef97badb084eb9ef8156a928c78a3284a6b6de23bd10.json).

Loot Tables now opens an item finder or a loot-table finder from the corresponding add button. Opening or cancelling the finder does not create a blank entry. Hidden interaction checks confirmed search filtering and that selecting a result adds the chosen name and correct entry type.
