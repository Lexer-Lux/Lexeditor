# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356292519 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/136

Created: 2026-08-06T02:13:45Z; updated: 2026-09-05T06:56:49Z

Exact metadata: [source record](sources/issue-5356292519-d1a9e8126dc35af72eb30698afae0f1db2ebe251cc2729c593c880911a7f4ca0.json).

SEPARATE TRINKETS VIEW — a trinket-only inventory view. Feasible, but a new
     tab inside Rockstar's satchel is not a data-only change: the satchel UI has
     fixed containers and hardcodes trinket handling. Either hook the runtime UI
     to add a native-looking category, or build our own inventory page. The
     filtering is easy; seamless insertion into the vanilla tab bar is not
     proven. See Lexer-Lux/Lexeditor#137.

## issue 5356292519 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/136

Created: 2026-08-06T02:13:45Z; updated: 2026-09-06T12:47:09Z

Exact metadata: [source record](sources/issue-5356292519-58713f56d609f040028b01fc86c8fd1f8c2bfe7a9656219476107755b84765c6.json).

Provide a separate trinket view without pretending a new native satchel category is already supported.

**Status: Research only.** Native category insertion still needs a feasibility test. Prepare a concrete native-tab or separate-page proposal before asking you to choose the presentation.

## comment 5550119421 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/136#issuecomment-5550119421

Created: 2026-08-06T03:56:48Z; updated: 2026-08-06T03:56:48Z

Exact metadata: [source record](sources/comment-5550119421-581b820a78a3a1180a84ad4cf2da9c562a17bb3ca77c0c687799a2ba8388e5f3.json).

Research result: the trinket list is easy; seamless insertion into Rockstar's satchel is the hard part. `satchel_ui_event_handler.c` builds fixed Satchel/category/menu/list databinding containers and separately hardcodes trinket/talisman handling. Catalog metadata cannot add a tab. Two routes remain: prove the authored movie accepts an injected category, or build a native-looking mod page containing only owned trinkets. Recommendation: one isolated datastore-injection probe; if focus, back navigation, or sizing breaks, use the mod-owned page.
