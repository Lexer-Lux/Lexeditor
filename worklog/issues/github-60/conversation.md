# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5290322475 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60

Created: 2026-08-30T04:21:29Z; updated: 2026-09-04T12:25:00Z

Exact metadata: [source record](sources/issue-5290322475-42f3643af006cd783a916547a89442cec009666670af0fe188617cf213c61380.json).

Replace the FF8 Characters Stat Growth coefficient list with one shared curve editor per stat.

Required layout:
- Separate HP, STR, VIT, MAG, SPR, SPD, and LUCK cards.
- A rectangular graph on the left with a fixed 0-255 visible range and levels 1-100.
- Exact minimum and maximum results above the graph.
- Four stored coefficient positions in a 2 x 2 grid on the right.
- The complete verified equation below the graph and controls.
- Editing a coefficient updates the graph and extrema immediately.
- HP c4 shows its stored value but remains read-only because the verified HP equation does not use it.
- The component must be reusable for Enemy curves; FF8 supplies only equations and theme overrides.

Acceptance:
- Rendered checks cover 1280 x 720 and 1600 x 900.
- Every card has four variables, a graph path, fixed axis labels, min/max output, and formula text.
- A live edit changes the graph without leaving the tab.
- A temporary-project coefficient edit saves and reads back without changing the installed baseline.

## issue 5290322475 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60

Created: 2026-08-30T04:21:29Z; updated: 2026-09-06T12:45:30Z

Exact metadata: [source record](sources/issue-5290322475-1bf635bd15c0c2ee54e412cf5b956f1c5c7093e65dc2282686a6e2ae161ec73a.json).

Character stat/XP curves, coefficient editing and live redraw are implemented. HP uses its appropriate larger range, not the original proposed 0–255 axis.

**Work remains:** fix the overlapping graph title/formula and white bar-mode fill; ensure GF graphs share the same layout. The requested larger title must remain clear of the equation. These are implementation fixes, not a request for another design approval.

## comment 5466857149 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5466857149

Created: 2026-08-30T05:11:32Z; updated: 2026-08-30T05:11:32Z

Exact metadata: [source record](sources/comment-5466857149-2e8e3d3760dc147be3d17b95eea966b6127d938e062733cb494ea39b3efdf663.json).

Character curves now use a 0–9,999 HP axis and 0–255 for the other stats. The four stored variables are labeled A–D and stacked in one narrow column. Graphs, min/max values, and Vanilla references now update while typing instead of waiting for the field to lose focus. Rendered checks passed at 1280×720 and 1600×900.

## comment 5470400723 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5470400723

Created: 2026-08-30T18:11:08Z; updated: 2026-08-30T18:11:08Z

Exact metadata: [source record](sources/comment-5470400723-7031cdc953b079eb6d0e51ba655e080b37d1f68336ab12a39e60d3a9d3fa7bdb.json).

Character Stat Growth now puts each equation and range in the card heading, hides the unused HP D value, and adds the verified XP curve with its two coefficients. Hidden renders at 1280x720 and 1600x900 measured 106 px-wide inputs and immediate graph and Vanilla-reference updates.

## comment 5470549581 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5470549581

Created: 2026-08-30T18:41:11Z; updated: 2026-08-30T18:41:11Z

Exact metadata: [source record](sources/comment-5470549581-3c321f8c60c9b62c8d9ed8a6fbffa6d09dde17e48a6651d533c73ed65ac1176b.json).

Every Character curve heading now uses one order: stat, range, formula. HP, standard stats, Speed, and XP share the same heading structure, and the formula truncates instead of forcing the range onto a new row. The curve save/readback and rendered geometry checks pass.

## comment 5472579403 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5472579403

Created: 2026-08-31T01:27:21Z; updated: 2026-08-31T01:27:21Z

Exact metadata: [source record](sources/comment-5472579403-ee9e8dce476adeb7f2b1acb9bb03156b38a2bb808954e9264da7dd36826fb352.json).

The curve cards now keep the equation in a fixed footer. A, B, C, and D live inside the graph and appear only on that graph's hover/focus; matching formula tokens highlight together, the curve redraws while typing, and graph hover reports the evaluated coordinate. Four enemy curves now fit per row without clipping. Rendered hover and save/readback checks pass.

## comment 5473982774 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5473982774

Created: 2026-08-31T05:06:11Z; updated: 2026-08-31T05:06:11Z

Exact metadata: [source record](sources/comment-5473982774-36584f81f8e1d9e13fe4e85989f564db684a33629fa7d4f8a49a483f8157e7f7.json).

The Character curve cards now use the whole card as the graph. The equation follows the live curve, the axes are inside it, hover swaps in the exact minimum and maximum, and a dotted guide plus X marks the evaluated point. A-D inputs slide down as one row from the top, with larger labels. The old card border, padding, and formula footer are gone. The 1600×900 render and coefficient save/readback checks passed.

## comment 5474323511 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5474323511

Created: 2026-08-31T05:53:13Z; updated: 2026-08-31T05:53:13Z

Exact metadata: [source record](sources/comment-5474323511-83bfadd45a610e2b0a72f8ee7db07ff167f99861428f686c83ae60d64c727ec5.json).

Cause: Arrow Up and Arrow Down changed the coefficient directly, while typed edits emitted the `input` event used by the shared graph redraw listener. The model changed, but the graph did not receive its redraw signal.

Arrow-key edits now use the same live-input path as typing. A hidden FF8 interaction check focused a STR coefficient, sent Arrow Up, and confirmed that the number and graph path both changed immediately while focus stayed in the same input. This applies to Character and Enemy curve controls that use the shared FF8 number input.

## comment 5474386420 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5474386420

Created: 2026-08-31T06:01:26Z; updated: 2026-08-31T06:01:26Z

Exact metadata: [source record](sources/comment-5474386420-2189a04c54ed80eb4e198e7c079d8c06b23ad39a2242a739ad8006f9e8018e1a.json).

Cause: the shared curve mapper treated helper classes named “variable name” and “variable overlay” as if they were A/B/C/D identities. That split the letter from its input, made empty drawer space activate a highlight, and left SVG formula letters without their intended colors.

The mapper now assigns identities only to real formula-variable tokens. Hovering either a variable letter or its input highlights the complete control and every matching letter in that graph's formula. Empty drawer space highlights nothing. SVG formula letters again use red A, blue B, yellow C, and green D. The hidden interaction check verified all three behaviors with four distinct rendered formula colors.

## comment 5474452215 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5474452215

Created: 2026-08-31T06:10:02Z; updated: 2026-08-31T06:10:02Z

Exact metadata: [source record](sources/comment-5474452215-033770ebbc4d94f7adf2790eb511afc6bf9c321d17189a43126221b1dfe93bb7.json).

The graph grid now consumes the complete Stat Growth content area. Its measured top and bottom match the available panel bounds, and both card rows reach the grid edges. Titles and the variable drawer remain overlays and reserve no graph space.

Long formulae now measure against the current SVG path and shrink only when they would exceed its safe span. The vertical offset was also moved from the `textPath` child, where Edge ignored it, to the actual SVG text element. The rendered check confirms all eight formula bounds stay inside the graph and above their curve lines. Current evidence: `worklog/issues/rendered/ff8-current-characters.png`.

## comment 5474470576 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5474470576

Created: 2026-08-31T06:12:14Z; updated: 2026-08-31T06:12:14Z

Exact metadata: [source record](sources/comment-5474470576-239ecc93793e35f14155fe9aa7453d50d34b20cd5ecbfda08406e9774d8d8f86.json).

The lower-left labels no longer share one baseline. The Y minimum now sits slightly above the corner, and the X minimum starts farther right. The rendered check measured both a vertical separation and an 18-pixel horizontal gap while keeping both labels inside the graph.

## comment 5539023904 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5539023904

Created: 2026-09-04T10:16:23Z; updated: 2026-09-04T10:16:23Z

Exact metadata: [source record](sources/comment-5539023904-7cad2359fe29105cad7a22e3b54997c1e1102edb82efbb1e308467974e5d3573.json).

Curve follow-up: bar mode must use the graph fill color instead of white. GF curves must share the current Character curve layout rather than an older side-drawer variant.

## comment 5539252973 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/60#issuecomment-5539252973

Created: 2026-09-04T10:38:37Z; updated: 2026-09-04T10:38:37Z

Exact metadata: [source record](sources/comment-5539252973-f090ee6bf32c9962a50ba968ab92025a5e71d82de7c48d9504f34b44ab4ab7f5.json).

Feature freeze for triage. The graph background title currently overlaps the curve formula. Make the title substantially larger while keeping it clear of the formula. Do not implement this until Lexer triages it.
