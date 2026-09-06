# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5264309580 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/19

Created: 2026-08-27T05:45:26Z; updated: 2026-09-05T06:00:40Z

Exact metadata: [source record](sources/issue-5264309580-d0367ee1edb6784ae45e92f71b12b161f044959bbb6b2e5eaa06d24961f4048d.json).

The RDR1 Items screen puts its list and detail pane above and below each other and leaves the right side empty.

The plugin must use the shared resizable list-detail grid: list on the left, divider in the middle, selected-item details on the right. The same repair must cover other RDR1 screens that use the obsolete rdr-split override.

## issue 5264309580 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/19

Created: 2026-08-27T05:45:26Z; updated: 2026-09-06T13:06:26Z

Exact metadata: [source record](sources/issue-5264309580-856edc91b399946ab6be09f3f8717cc6ff248cdd5d633805af0dd68627ed4f46.json).

**Status: Layout and row-fitting fixes are ready for review.** Items, Shops and Missions should show complete entries, with details on the right.

- [ ] Restart Lexeditor and open RDR1 Items. Select a record and drag the divider; confirm both panels remain usable without an empty right half.
- [ ] Check Items, Shops and Missions at 1600×900 and 1280×720. Confirm the bottom list entry is complete and paging works. Report the affected view and screenshot.

## issue 5264309580 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/19

Created: 2026-08-27T05:45:26Z; updated: 2026-09-06T13:06:26Z

Exact metadata: [source record](sources/issue-5264309580-96936019683ceaca2d75ed1081707f94f8d47328c371088167281d27ae5df841.json).

**Status: Layout and row-fitting fixes are ready for review.** Items, Shops and Missions should show complete entries, with details on the right.

- [ ] Restart Lexeditor and open RDR1 Items. Select a record and drag the divider; confirm both panels remain usable without an empty right half.
- [ ] Check Items, Shops and Missions at 1600×900 and 1280×720. Confirm the bottom list entry is complete and paging works. Report the affected view and screenshot.

## comment 5435213652 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/19#issuecomment-5435213652

Created: 2026-08-27T06:27:07Z; updated: 2026-08-27T06:27:07Z

Exact metadata: [source record](sources/comment-5435213652-b95ab187fd00e3de467f24f84f658c7a514056074646b30498dc58daa50f9816.json).

Fixed the RDR1 Items layout. The plug-in no longer replaces the shared list-detail grid, so the list and details are side by side with the draggable divider between them. Hidden Chromium confirmed both panels on one row with no empty right half.

## comment 5549836078 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/19#issuecomment-5549836078

Created: 2026-09-05T06:00:40Z; updated: 2026-09-05T06:00:40Z

Exact metadata: [source record](sources/comment-5549836078-56f47a6a0cf835d2e88235dd12c400b887576dd906aead33942a416488fcfda7.json).

RDR1 Items, Shops, and Missions now reduce the number of rows when the window is too short to show complete entries. Hidden tests passed at 1600×900 and 1280×720. Items also has field help buttons; the scalar-editing note stays in Data Map. Restart Lexeditor and check the bottom entry in these lists.
