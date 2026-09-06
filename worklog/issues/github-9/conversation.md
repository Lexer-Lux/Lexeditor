# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5202503114 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/9

Created: 2026-08-20T10:42:47Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5202503114-11cb5b7cd960e0b682e1e550bba7e07698289e46bd3098d5474df7f70500aafd.json).

Create one shared code-level New/Add button component so plugins do not hand-build plus controls. The component is icon-only, keeps its action in the tooltip and accessible label, and lets each game theme own its appearance.\n\nFor RDR2, use the current dashed + Rule treatment as the base, but show a larger plus with no visible text. Route every create/add action through it, including New Item, New Effect, Effects, Tags, carry rules, quick-select slots, recipes, ingredients, shop conditions/groups/items, loot tables/entries, yields, rows, and challenge rewards.

## issue 5202503114 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/9

Created: 2026-08-20T10:42:47Z; updated: 2026-09-06T13:06:16Z

Exact metadata: [source record](sources/issue-5202503114-6334eac6d499f5b81bef31756160dc1248f9e53c20e0bdf799eecb66eee9a3fe.json).

Use the same clear, icon-only + button for new items, effects, tags, recipes and other entries. Hover text names the action.

**Status: Implemented; needs your visual check.**

- [ ] Restart Lexeditor and open RDR2 Items. Check the + buttons for Effects, Tags and an empty Recipe field: each should be centered, readable and identify its action on hover.
- [ ] In a copy of your mod, add then remove a tag or quick-select assignment. Confirm the correct row changes; report any broken button or clipping.

## comment 5354871102 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/9#issuecomment-5354871102

Created: 2026-08-20T10:49:54Z; updated: 2026-08-20T10:49:54Z

Exact metadata: [source record](sources/comment-5354871102-98e223fdc0595759c5520528c4d1b6587fdeabfdfc728dabb868783842176b62.json).

Implemented one shared `LexeditorUI.newButton()` component and routed 21 RDR2 create/add actions through it. RDR2 now renders the control as one icon-only 34×30 dark button with a dashed border and a 23 px plus; the exact action stays in the tooltip and accessible label.

The complete hidden RDR2 and Warband render suite passed. It measured the same control in the Items toolbar, prices, carry rules, quick-select, Effects, and Tags, and it exercised quick-select add/remove with no browser errors or live-file changes.

## comment 5393940440 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/9#issuecomment-5393940440

Created: 2026-08-24T10:27:09Z; updated: 2026-08-24T10:27:09Z

Exact metadata: [source record](sources/comment-5393940440-db3eac19a3ba2fb785af634409c6a079b8ef6a9769c4d3bde24e56c8832ae137.json).

Fixed the shared RDR2 Add/New plus. It now uses the installed Redemption display face at 27 px instead of the neutral Windows symbol font. I also added a painted-glyph metric check: the first RDR-font render was 3 px high, and the final theme correction measures exactly centered across all seven representative buttons. The full RDR2/Warband UI suite passed.

## comment 5393975576 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/9#issuecomment-5393975576

Created: 2026-08-24T10:30:37Z; updated: 2026-08-24T10:30:37Z

Exact metadata: [source record](sources/comment-5393975576-b789c1a4f8d7724b6e5823c76845e29ce5a75a77838df2a3cc03a649bad49c35.json).

The empty Recipe field in Items now uses the shared + icon. Existing recipe counts remain links because they open existing data. Hover text and the accessible name both say \Add recipe\. The direct Recipe-field render check and the complete hidden RDR2/Warband suite passed.
