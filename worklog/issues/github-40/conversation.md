# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286557217 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/40

Created: 2026-08-29T12:37:15Z; updated: 2026-09-04T12:24:48Z

Exact metadata: [source record](sources/issue-5286557217-e0074a52bdc6ba9bde9721f0bc72e4e6b49de1673563a6beac053b2f95175788.json).

The FF8 Shops detail pane must fit every engine shop slot without internal scrolling.

Compact and auto-size the right-side detail layout so every engine shop slot remains visible at once. Reduce nonessential padding and gaps, fit the title/capacity/list controls to the available height, and keep all controls legible and usable. Separators appear only between stock entries; the last entry has no trailing divider.

Acceptance:
- A 16-slot shop shows its title, capacity, header, and every item row at once.
- The right detail pane has no vertical scrollbar and does not respond to wheel scrolling.
- Item selectors, Rare controls, remove buttons, provenance controls, and Add remain usable.
- Entry separators do not draw below the final row.
- The pager and left list remain unchanged.


## issue 5286557217 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/40

Created: 2026-08-29T12:37:15Z; updated: 2026-09-06T13:16:37Z

Exact metadata: [source record](sources/issue-5286557217-19edd7425fecdc79a4b807aefa370274c13ff7e3a2c4a5f146a62784098dc7cb.json).

**Status: Closed after the fitting repair.** A full shop displays its title, controls and all sixteen stock rows without internal scrolling or a clipped last entry. Separators appear only between entries; the final rendered checks covered both requested desktop sizes.

## comment 5462503012 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/40#issuecomment-5462503012

Created: 2026-08-29T12:48:22Z; updated: 2026-08-29T12:48:22Z

Exact metadata: [source record](sources/comment-5462503012-825da2833322bc096e98045c0c7b2036b65002ea14ead6160fd38c883d64eaaa.json).

The Shops detail pane now fits every one of its 16 engine slots without scrolling. I moved the capacity into the title row, reduced the unused padding, kept each selector and source value on one line, and made the 16 stock rows divide the available height automatically.

The layout passed rendered checks at 1280×720 and 1600×900. Both sizes kept all selectors, Rare controls, remove buttons, Vanilla/reference controls, and Add present; the detail pane had no overflow and did not move on wheel input.

## comment 5464923300 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/40#issuecomment-5464923300

Created: 2026-08-29T21:14:34Z; updated: 2026-08-29T21:14:34Z

Exact metadata: [source record](sources/comment-5464923300-9581bb052f8bf73f17ea403d7dd2f588119379d22ada0994d61b95813167aa90.json).

Shop and recipe lists now draw separators only between entries. The last entry has no trailing line. The 16-slot Shops panel still fits without scrolling at 1280 x 720 and 1600 x 900.

## comment 5466538546 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/40#issuecomment-5466538546

Created: 2026-08-30T03:45:35Z; updated: 2026-08-30T03:45:35Z

Exact metadata: [source record](sources/comment-5466538546-b521b37bbbd79e116a204591261f6f3931d594225a9c38ebf20851011e9c7dee.json).

Follow-up Shops cleanup: the separate remove column is gone. Hovering a slot number now reveals a red X; clicking it sets that slot to Nothing. Item icons now live inside the item control, and reference values show the same icon-and-name form without moving the control. All 16 slots still fit without scrolling.

## comment 5471521451 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/40#issuecomment-5471521451

Created: 2026-08-30T22:01:31Z; updated: 2026-08-30T22:01:31Z

Exact metadata: [source record](sources/comment-5471521451-0c6e04a9a8985968e1b48c0cce50908d0997b76ee88aeb7cd83317b7df579bd0.json).

The recurrence came from a later fixed-row rule. Shops now divides the available right-panel height between the header and all 16 stock rows. Hidden renders at 1280x720 and 1600x900 show no gray footer, scrollbar, clipped control, or last-row divider.
