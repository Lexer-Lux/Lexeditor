# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286407734 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/36

Created: 2026-08-29T11:58:52Z; updated: 2026-09-04T12:24:44Z

Exact metadata: [source record](sources/issue-5286407734-4761f63023b9dc5f101fbf33eebf950398e618bffdc2b22fe8f5413d9efb5583.json).

The FF8 Weapons detail pane must show its two main editing areas at once without right-pane scrolling.

Make Data the first always-visible section and Cost the next always-visible section. Cost contains the upgrade's monetary cost and ingredient rows. Do not use collapsible sections. Keep typed editors, vanilla/reference/source controls, and save/readback behavior intact.

Acceptance:
- Data and Cost are both fully visible at a representative desktop size.
- Cost shows the monetary cost and every ingredient quantity.
- The right pane has no wheel scrollbar.
- Save/readback preserves cost, ingredients, and weapon data.


## issue 5286407734 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/36

Created: 2026-08-29T11:58:52Z; updated: 2026-09-06T13:16:31Z

Exact metadata: [source record](sources/issue-5286407734-3d783f9d981887086f6220b5bb0ddaafe1cc6d9901004da31506fb49f36f4ddb.json).

**Status: Closed after the layout repair.** Weapon Data and Cost stay visible together, including money and ingredients. Reference values share aligned lanes; ingredient selectors and quantities form one row without unnecessary inner scrolling.

## comment 5462312889 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/36#issuecomment-5462312889

Created: 2026-08-29T12:04:03Z; updated: 2026-08-29T12:04:03Z

Exact metadata: [source record](sources/comment-5462312889-c78243d715540770df2b693eed0bf8ef04023d1985d39d64e4e77686aa5ac87c.json).

Weapons now keeps Data at the top and Ingredients directly below it. Both sections stay open, and the right pane no longer has its own wheel scrollbar. All typed editors and the vanilla/reference restore controls remain in place; upgrade price, recipe quantity, and attack power also passed a temporary-project save/readback check.

At 1600 × 900, the complete pane fits with no clipped descendants or hidden overflow. Please inspect the Weapons pane at your usual window size.

## comment 5464923054 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/36#issuecomment-5464923054

Created: 2026-08-29T21:14:31Z; updated: 2026-08-29T21:14:31Z

Exact metadata: [source record](sources/comment-5464923054-c06dad5a2f5dbb83332bd848fc5e5f684c4de02923568289ec2c130dc4b3f504.json).

Weapons now shows Data followed by Cost. Cost includes the Gil upgrade price above the four ingredient rows, with the existing reference/restore controls intact. Save/readback and the 1600 x 900 no-scroll render passed.

## comment 5487506302 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/36#issuecomment-5487506302

Created: 2026-09-01T01:49:09Z; updated: 2026-09-01T01:49:09Z

Exact metadata: [source record](sources/comment-5487506302-9bbf19ea607e496820e86dfd44d4c3a31af1f3da72c568ab4ae33fb669af98a8.json).

Repaired the Weapons detail regression without reopening this completed issue. Data controls now use internal reference lanes so every field reaches the same right edge. Cost item selectors meet their amount controls, all amount controls share the right edge, Nothing spans the full row, the Cost title is visible, and the panel has no horizontal overflow.
