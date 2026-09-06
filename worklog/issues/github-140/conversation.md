# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356293475 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/140

Created: 2026-08-06T02:20:16Z; updated: 2026-09-05T06:57:02Z

Exact metadata: [source record](sources/issue-5356293475-d13f37f993f2450683b40183429a35049bfca99fb47fa4050546c1f6aa98c061.json).

STORE DISPLAYS MATCH STOCK — the buyable in-store physical displays should
     reflect each shop's new stock, if possible.

Is there even enough space to do that? Do the displays contain all the stock even in vanila?

## issue 5356293475 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/140

Created: 2026-08-06T02:20:16Z; updated: 2026-09-06T12:47:17Z

Exact metadata: [source record](sources/issue-5356293475-22a364a2f4d216df12039b634eb9faf5c483ce71bb02fdd9c796ce9ef356e20d.json).

**Status: Design decision needed.** Shops have more menu stock than physical display positions, so automatic one-to-one shelving is not established.

- [ ] Choose between representative displays—remove discontinued categories and place selected signature items—or a larger custom display system. For representative displays, name the first shop and the few items/categories you want visible.

## issue 5356293475 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/140

Created: 2026-08-06T02:20:16Z; updated: 2026-09-06T13:54:12Z

Exact metadata: [source record](sources/issue-5356293475-d6c7af49a66c3b5d9076331e98f4971c1e38b0236c5cbfcfcc150cbb050b345f.json).

**Status: Design decision needed.** Shops have more menu stock than physical display positions, so automatic one-to-one shelving is not established.

- [ ] Choose between representative displays—remove discontinued categories and place selected signature items—or a larger custom display system. For representative displays, name the first shop and the few items/categories you want visible.

## comment 5550120506 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/140#issuecomment-5550120506

Created: 2026-08-06T03:57:53Z; updated: 2026-08-06T03:57:53Z

Exact metadata: [source record](sources/comment-5550120506-4d009ab59cd666c0c528b1a624b15ec31cd4f80cf04e09273c1fb2cf68c35964.json).

Research result: only partially feasible. Shop inventory and physical displays are separate: `shopsinventories` controls menu stock, while shelves/counters are authored props plus scripted inspect/buy points. Vanilla already sells more entries and variants than it physically displays, so space and one-to-one mapping do not exist. A practical version is representative stock: remove displays for categories no longer sold and hand-place/bind limited signature items. Automatic full mirroring needs a runtime display manager plus per-interior collision, navmesh, robbery, mission, and streaming tests. Recommendation: category-level/signature-item consistency.
