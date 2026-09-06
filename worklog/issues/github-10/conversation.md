# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5202578748 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/10

Created: 2026-08-20T10:51:37Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5202578748-8e855e5856d73e6208bbcff97a7f051e751bb9df5781fcf686716d5f99578619.json).

## Requested behavior

Add one shared draggable divider to the reusable list-detail view: the selectable record list on the left and selected record editor on the right. Dragging the divider changes the panel widths. Plugins must not implement their own resize logic.

## Acceptance

- The shared framework owns the divider, drag behavior, keyboard adjustment, bounds, and saved width.
- Each list-detail view can use its own saved split.
- Items, Crafting, Loot Tables, Weapons, and Warband list-detail screens receive the behavior from the shared preset.
- The divider has a clear hover/drag state and an accessible separator role.
- Double-click resets the view to its default split.
- Narrow stacked layouts hide the divider.
- Resizing does not break fitted page capacity, selection, paging, or the no-scroll left-list rule.

## issue 5202578748 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/10

Created: 2026-08-20T10:51:37Z; updated: 2026-09-06T13:06:18Z

Exact metadata: [source record](sources/issue-5202578748-628b8da9ba87bcf1f5cacec4a65d3c06b29fbeba2c7d8a43b7266857495943cd.json).

**Status: Implemented; needs your check.** Panel widths are saved separately for each view.

- [ ] Open RDR2 Items, drag the divider, switch to Crafting and back. Confirm Items remembers its width and selection.
- [ ] Double-click the divider to reset it. Focus it and use the arrow keys; confirm resizing works without clipped rows or a list scrollbar.
- [ ] Narrow the window until panels stack. Confirm the divider disappears; report any overlap or paging jump.

## comment 5354941383 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/10#issuecomment-5354941383

Created: 2026-08-20T10:57:03Z; updated: 2026-08-20T10:57:03Z

Exact metadata: [source record](sources/comment-5354941383-f6b0ec7190df6a0464de1442d901d455af90dcabe77e8f4216007452417638fa.json).

Implemented this in the shared list-detail base, not in individual screens. The divider supports mouse dragging, Arrow/Home/End keys, Shift for larger steps, per-view saved widths, bounded panel minimums, and double-click reset. Narrow stacked layouts hide it.

Items, Crafting, Loot Tables, Weapons, Warband Manuals, and Warband Settings now inherit it. The hidden render dragged Items by 150 pixels, rebuilt the view and restored the width within two pixels, kept the fitted left list scroll-free, and held page 2 stable for 180 frames with no browser errors or live-data changes.

## comment 5354994845 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/10#issuecomment-5354994845

Created: 2026-08-20T11:02:47Z; updated: 2026-08-20T11:02:47Z

Exact metadata: [source record](sources/comment-5354994845-0699a0fb20e548066f313daacc5e5fdca08fe265464c48157a7ab67d571c46d0.json).

Correction: my earlier statement that Crafting inherited the standard view was incomplete. It inherited the outer shell and pager, but still inserted a custom table as its left panel.

That table is now replaced with the shared selectable-list master used by Items and Loot Tables. Crafting keeps sortable Item, Category, and Recipes columns, and now uses the standard list rows, selection appearance, detail panel, divider, fitted no-scroll rows, and bottom pager. The full hidden RDR2/Warband suite passed after rendering Crafting directly: 13 complete rows fit with no vertical overflow and no browser errors or live-data changes.
