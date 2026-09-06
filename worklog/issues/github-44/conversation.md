# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286701842 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44

Created: 2026-08-29T13:10:25Z; updated: 2026-09-04T12:24:52Z

Exact metadata: [source record](sources/issue-5286701842-7f9d34d4b8a129d48e6a6bb95f83e4e6e648f9908aeae1b71e8badbfba476256.json).

Add a shared N-barrelled table mode to paged list-detail views. A barrel is one existing table page; additional barrels show the next consecutive pages side by side.

Acceptance:
- A compact minus/count/plus control changes the number of barrels.
- Each barrel repeats the same sortable table header and row capacity.
- Consecutive old pages appear left to right.
- Pagination counts groups of barrels and hides when all records fit in one group.
- Selection and the right detail panel work from every barrel.
- Wheel and pager navigation move one barrel group at a time.
- Barrel count is stored locally per Windows user, game, and view; it is not saved in a mod project or shared across views.
- The shared list-detail preset owns the behavior.
- Rendered checks cover one, two, and three barrels plus persistence and responsive bounds.

## issue 5286701842 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44

Created: 2026-08-29T13:10:25Z; updated: 2026-09-06T13:16:44Z

Exact metadata: [source record](sources/issue-5286701842-6565a2e604ed9f78f71d6a756307015c3c3cfcaf6fe41a2e0cec8060b164676f.json).

**Status: Closed after implementation.** The per-view barrel control shows consecutive pages side by side with shared sorting and selection. Counts persist independently; its adjustment popup stays open while the pointer is over the control.

## comment 5462646482 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44#issuecomment-5462646482

Created: 2026-08-29T13:20:39Z; updated: 2026-08-29T13:20:39Z

Exact metadata: [source record](sources/comment-5462646482-feed674951a43cba84df0aefd1bd410bdace43a4bc87cb296e383195692197d6.json).

The shared list-detail view now supports 1-6 consecutive table barrels. The compact minus/count/plus control sits above the table area, later-barrel rows open the same detail pane, and the bottom pager disappears when one barrel group contains all results. Lexeditor saves the count locally for each game and view, so changing FF8 Magic does not change Items or another plugin. Restart Lexeditor once, then please check the control placement and table readability in your normal window size.

## comment 5464105796 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44#issuecomment-5464105796

Created: 2026-08-29T18:25:43Z; updated: 2026-08-29T18:25:43Z

Exact metadata: [source record](sources/comment-5464105796-7c2cccc7ed9ec4caeb0a07e035aafb05487c6740278ce5de780f0cbd4fb5f442.json).

Fixed the barrel control. FF8's inherited text shadow was duplicating the + and - glyphs. They are now drawn symbols with no text shadow, and the whole control appears only while its table area is hovered or focused.

## comment 5464441184 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44#issuecomment-5464441184

Created: 2026-08-29T19:37:25Z; updated: 2026-08-29T19:37:25Z

Exact metadata: [source record](sources/comment-5464441184-3d18b34d8b2bba01e836113b733823d35f3b35ee47119dc0bdc12cd4cc251dc6.json).

The thin and clipped barrel panels were a regression from the shared panel-composer migration: the barrel preset calculated a wider minimum, but the two-panel adapter no longer used it. The adapter and composer now enforce that minimum during initial layout, restored layout, window resizing, mouse dragging, and keyboard resizing. Each added barrel reserves another complete table width plus its gap, and the column tracks contract within the available barrel instead of clipping the last column or right border. Rendered checks passed with one and three barrels at 1280x720 and 1600x900, including dragging the divider fully left.

## comment 5464680083 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44#issuecomment-5464680083

Created: 2026-08-29T20:21:03Z; updated: 2026-08-29T20:21:03Z

Exact metadata: [source record](sources/comment-5464680083-f869c1e6fede3ccce33e09d56994549ec1f06df93fed27d3ecfd881910563fc6.json).

Move the barrel control into the shared divider hover rail. Rotate it 90 degrees counter-clockwise, place BARRELS before the minus/count/plus group on its rotated axis, center it along the table height, and reveal it only with the divider rail. Right-click resets the split; double-click must no longer reset it.

## comment 5464858366 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44#issuecomment-5464858366

Created: 2026-08-29T21:00:59Z; updated: 2026-08-29T21:00:59Z

Exact metadata: [source record](sources/comment-5464858366-a896abc8649f377f421c22405d6f8aa4da3111b9f9a105abaee003ab8d26f506.json).

The barrel control now lives beside the shared resize handle, rotates 90 degrees counterclockwise, stays hidden until that rail is active, and places BARRELS above the vertical controls. Right-click resets the split; double-click no longer does. Rendered checks passed at 1280×720 and 1600×900.

## comment 5466538613 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44#issuecomment-5466538613

Created: 2026-08-30T03:45:36Z; updated: 2026-08-30T03:45:36Z

Exact metadata: [source record](sources/comment-5466538613-b19ac6478fe9e9edfdd4be130780d75d882085b390b51124ffcb7b72ea82dc00.json).

Fixed the shared barrel rail input bug. The divider no longer captures minus or plus clicks, and the control now touches the divider rail instead of overlapping it. Adding and removing barrels works in the rendered FF8 view, including at 1280 x 720 and 1600 x 900.

## comment 5466776185 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/44#issuecomment-5466776185

Created: 2026-08-30T04:49:40Z; updated: 2026-08-30T04:49:40Z

Exact metadata: [source record](sources/comment-5466776185-b662d78555b3440d685ac8db863c20caa5ad29fb992f999f44e37aafa09397c5.json).

The Barrels control now stays open after plus or minus and closes only when the pointer leaves it. This supports repeated changes without reopening the control. The shared rendered contract passes at 1280x720 and 1600x900.
