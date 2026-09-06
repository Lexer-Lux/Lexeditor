# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286672980 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/43

Created: 2026-08-29T13:04:52Z; updated: 2026-09-04T12:24:51Z

Exact metadata: [source record](sources/issue-5286672980-e5ac108406a4060e69fd922536008061706522a7bbab911bb85935b9b7acd037.json).

Make numeric record identity consistent across LEXEDITOR lists.

Acceptance:
- If a record list has a numbered ID column and a name column, ID appears immediately before Name.
- Name remains the default sort unless a user selects another column.
- The rule lives in the shared column-list component and is reused by plugins.
- Non-numeric technical keys are not reclassified as numbered IDs.
- Current FF8 numbered lists follow the rule without width or overflow regressions.

## issue 5286672980 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/43

Created: 2026-08-29T13:04:52Z; updated: 2026-09-06T13:16:42Z

Exact metadata: [source record](sources/issue-5286672980-904b41ada478753a346f86338b96abf83bb5562dad161389c0b288545798f33c.json).

**Status: Closed after implementation.** Numeric ID columns precede Name while Name remains the default sort. IDs use a consistently darker treatment in lists and details; nonnumeric technical keys are not treated as numbered IDs.

## comment 5462589766 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/43#issuecomment-5462589766

Created: 2026-08-29T13:08:10Z; updated: 2026-08-29T13:08:10Z

Exact metadata: [source record](sources/comment-5462589766-844ac68ffef97e6550ac0d5e37a02b3e0d1460885f3862c2c60150155334fa33.json).

Numeric record IDs now appear immediately before Name through the shared column-list component. FF8 Items, Shops, Weapons, Magic, and Enemies now show ID first while Name remains the active default ascending sort. The shared rule does not move string keys such as `itm_alpha`. I checked all five FF8 views at 1280×720 and 1600×900 with no width or overflow regression.

## comment 5462928019 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/43#issuecomment-5462928019

Created: 2026-08-29T14:21:14Z; updated: 2026-08-29T14:21:14Z

Exact metadata: [source record](sources/comment-5462928019-ad14b86716a9b1c4de8458ead9ad7a64ef93c620cd59f27d138e9d3985d1e0ac.json).

Numbered IDs now use one shared prefix-unit component. Lists and detail headings show exactly one # before the value in a darker, muted shade. FF8 Items, Shops, Weapons, Magic, Enemies, and GF General use it. Name remains the default sort, and technical keys such as itm_alpha are not changed. Hidden-window checks passed at both tested sizes with no overflow.

## comment 5464135473 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/43#issuecomment-5464135473

Created: 2026-08-29T18:32:03Z; updated: 2026-08-29T18:32:03Z

Exact metadata: [source record](sources/comment-5464135473-55e13abaee28462ba0f9eb88861ee3d66ae8eda388c4ebdfd313950cc2fefa9f.json).

Fixed the FF8 detail ID color. A local white-text rule overrode the global darker ID component, and the old detail test checked only the ID text. The shared ID color is now authoritative, and the rendered test requires list and detail IDs to be darker than names and titles in Items, Shops, Weapons, Magic, and Enemies.
