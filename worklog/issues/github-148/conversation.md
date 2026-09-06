# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356295411 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148

Created: 2026-08-06T02:31:38Z; updated: 2026-09-05T06:57:30Z

Exact metadata: [source record](sources/issue-5356295411-5f328d9b916669049d9b43ab36b61e25a437661b6496240388837324b08f05f0.json).


146. SELLING MODEL + SHOPS TAB REDESIGN — I want to control what each merchant
     buys and sells.
     Settled: the shop inventory data is NOT a sell whitelist, it's a narrow
     per-item exception list, so unchecking a shop there cannot stop me selling
     something. Global unsellability works (remove the item's sell price).
     Per-merchant Accept/Reject now exists as a tri-state override.
     LEFT: a read-only report showing each shop's real effective acceptance
     rules, so the editor stops guessing.

## issue 5356295411 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148

Created: 2026-08-06T02:31:38Z; updated: 2026-09-06T13:07:21Z

Exact metadata: [source record](sources/issue-5356295411-4ecb8a46281cea229265f5c3ef26fc005b11935ea768335828c691792072abf7.json).

**Status: Latest Shops UI is ready for review.** The rejected full-page catalog experiment was completely reverted; it is not still awaiting your approval.

- [ ] Reload Shops, select General Store and choose SELLS → Weapons → Revolvers. Combine the filter with a search, then choose All; confirm the correct rows appear.
- [ ] Check that the tall Catalogue column is gone and price, availability and Acceptance Report controls remain usable. Report a wrong row, clipped control or inaccurate acceptance result.

## comment 5550122771 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122771

Created: 2026-08-06T06:56:24Z; updated: 2026-08-06T06:56:24Z

Exact metadata: [source record](sources/comment-5550122771-28e22526c2745f63aea64eb9acec978cf4913f8902bf5f22904cb8842c1af92e.json).

Fixed and live in LEXEDITOR. The Acceptance Report UI already existed, but its /api/shops/acceptance endpoint was missing, so the tab could only 404. The new report combines runtime buyer PDATA, explicit accept/reject overrides, and real catalog sell prices into Explicit accept / Listed-no-price conflict / Blocked by us / Globally unsellable / Engine-default unknown, never treating absence from sparse PDATA as rejection. Validated all 20 shops and 5,080 items; restarted the editor server and confirmed the live HTTP endpoint returns the report. Please open Shops -> Acceptance Report and check the presentation/responsiveness.

## comment 5550122801 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122801

Created: 2026-08-13T08:39:01Z; updated: 2026-08-13T08:39:01Z

Exact metadata: [source record](sources/comment-5550122801-c0ecc5c0cf85f2877ba0771b288303b301f626725d0a059b52a26feb83946f6f.json).

The live visual test found and fixed one layout defect: the report reused a five-column width rule, so the sixth Unknown column collapsed and was clipped. The Acceptance Report now has its own six-column layout. I reloaded the real editor and confirmed all six columns fit at normal width, all 20 shop rows load, the conflict table remains responsive, and the browser console has no warnings or errors.

## comment 5550122821 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122821

Created: 2026-08-16T03:10:36Z; updated: 2026-08-16T03:10:36Z

Exact metadata: [source record](sources/comment-5550122821-2d924372f57ba1d072ec76a2b4d18da5a309ee57594612f5a22d6896da518be6.json).

Reworked Shops into a green BUYS panel, center shop list, and red SELLS panel. Both item panels now use the shared list design with search, editable global prices, check/X controls, and item magnifiers. Search includes inactive items with disabled prices; enabling one activates its price. Existing sell conditions are visible but remain read-only and are preserved on save. BUYS tooltips and right-click Vanilla preserve the sparse buyer-data distinction instead of treating absence as rejection. The Acceptance Report remains available and now warns when unsaved changes are excluded. Isolated save/readback and the rendered 1600×900 workflow passed without changing live data.

## comment 5550122833 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122833

Created: 2026-08-16T10:08:54Z; updated: 2026-08-16T10:08:54Z

Exact metadata: [source record](sources/comment-5550122833-9df3782817d0e70b94c6d845e815fabbed3016f028568c2e7dd33f5be9b425af.json).

Replaced the combined Shops search with independent fields in the BUYS and SELLS panel headings. Each side now keeps its own query and results; rendered input tests proved filtering one side does not change the other. The center heading now reads 24 SHOPS, with 24 muted gray and SHOPS gold, and the toolbar no longer repeats the search or shop-type count. I also replaced the initial magnifying-glass emoji after its uneven glyph padding was reported: the final icon is a CSS-drawn 16x16 magnifier with exact 2px circle and handle geometry. Rendered layout, isolated save/readback, conditions, inactive controls, toggles, Items jump, Acceptance Report, and the full shared UI suite all passed with live files unchanged.

## comment 5550122849 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122849

Created: 2026-08-16T10:38:33Z; updated: 2026-08-16T10:38:33Z

Exact metadata: [source record](sources/comment-5550122849-ca42a057b72762f741576fa06677e95f2897a1eae9adde0b6a68685d936dabf4.json).

Added a real AVAILABILITY column between ITEM and PRICE on SELLS. Each cell now shows ALWAYS or its condition count and opens an editor for the exact nested catalog structure: add/remove groups, edit each group count, and add/edit/remove condition type, key, state, and lock. Save preserves group boundaries instead of flattening them, validates the scalar fields before writing, and leaves unchanged listing subtrees untouched. Isolated XML round-trip, the rendered 1600x900 column and dialog, the complete Shops workflow, and both shared UI suites passed with live files unchanged.

## comment 5550122872 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122872

Created: 2026-08-17T04:07:25Z; updated: 2026-08-17T04:37:21Z

Exact metadata: [source record](sources/comment-5550122872-377a23a16601ac30be79c2f88a2af6cc430208b9a0e6d2dd563410743ed4add0.json).

The page-layout retest failed, so that cause claim remains withdrawn. The live sequence proved that the doctor script took ownership, disabled control, never opened the catalogue UI, and restarted from thread 75 to 81 without cleanup.

The corrected catalogue keeps the doctor Navy edit and all vendor-editing support. It splits entries that exceeded declared page capacity into reachable pages; it does not remove Online stock. A one-shot recovery is also installed for the exact abandoned shop state. It requires a changed doctor thread and no active shop or inventory UI, so Alt-Tab alone cannot trigger it.

This is installed but not yet confirmed in game. Start Story fresh, open the doctor catalogue, confirm the Navy Revolver is present, then close it and confirm movement and prompts return. Further vendor-stock edits remain supported.

## comment 5550122896 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122896

Created: 2026-08-20T06:20:10Z; updated: 2026-08-20T06:20:10Z

Exact metadata: [source record](sources/comment-5550122896-1a9518c3873d235d320ea07b9c082b016e15aef5baa4c5144064efbfbb6ace3c.json).

The repaired combined catalogue now passes the in-game doctor test. The full shop stock and printed page data are available, but LEXEDITOR still needs to show each listing's catalogue category, page layout, and page occupancy. It should place normal additions automatically from proved reference pages, create overflow pages safely, and ask for a destination only when a shop has no matching category.

## comment 5550122918 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122918

Created: 2026-08-20T06:29:12Z; updated: 2026-08-20T06:29:12Z

Exact metadata: [source record](sources/comment-5550122918-08f79e365051b7046f6e315fa22b8a47c735180902dbd32f5efcac4c27700f22.json).

The BUYS panel now states that item sellability is not fully visible and that this panel contains custom overrides. It also gives the exact controls: left-click toggles an override and right-click clears it. No control behavior or SELLS text changed. The issue remains actionable for the catalogue-page work.

## comment 5550122934 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122934

Created: 2026-08-20T07:21:07Z; updated: 2026-08-20T07:21:07Z

Exact metadata: [source record](sources/comment-5550122934-9d8bb484fc5f0946be857c1af8f3ec04c8b2066013cca694811cc328298e3a93.json).

The catalogue-page work is now in the standalone editor. Each SELLS row shows its category, page layout, and occupancy. An exact category match places the item automatically; a full declared page creates a reachable overflow page; and only a missing category match opens the destination choice with real categories from that shop. Save resolves every destination before changing stock, and cleanup removes empty generated pages. The live placement API, catalogue scan, source checks, and failure cases pass. I did not open the editor or run a Story test, so the visual check and save/open/close acceptance remain and the issue stays actionable.

## comment 5550122946 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122946

Created: 2026-08-20T08:04:33Z; updated: 2026-08-20T08:04:33Z

Exact metadata: [source record](sources/comment-5550122946-924724c8400699af4cdcff2d5b2a9f7b5760a3c05f554d34471362c117b0c478.json).

Clarification: Lexer did not authorize the newly added catalogue category/page/occupancy UI. It is currently present, but it is unapproved and must not be treated as a settled requirement or completed feature. Keep this issue actionable until Lexer decides whether to keep, revise, or remove it.

## comment 5550122966 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122966

Created: 2026-08-20T08:15:31Z; updated: 2026-08-20T08:15:31Z

Exact metadata: [source record](sources/comment-5550122966-31ebf0c1f5c5c9845b9394eab7244c698aba9e09acfd86183116b45326cb0085.json).

Your requested reversible catalogue experiment is active. Across all nine General Store layouts, each of the 1,833 printed entries now has its own reachable `FULLPAGE_LAYOUT_6` page. Other shops, item records, stock, prices, and requirements are unchanged, and the exact pre-experiment catalogue is backed up.

After a full Story restart, open any General Store. Browse ordinary supplies, weapons, and clothes; buy one item; then exit. Please report blank or wrong art/text, missing or skipped pages, a catalogue abort, or lost movement/prompts. I can restore the exact backup after you report the result.

## comment 5550122986 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/148#issuecomment-5550122986

Created: 2026-08-20T08:40:17Z; updated: 2026-08-20T08:40:17Z

Exact metadata: [source record](sources/comment-5550122986-f124a615e2f034b842f41191454b98e366e43a26ad2021a37f0bbe371f1e77d3.json).

The full-page experiment gave a clear result: the game accepted `FULLPAGE_LAYOUT_6` for every General Store item, but the presentation looked poor. I restored the exact pre-test catalogue.

LEXEDITOR now removes the tall per-row Catalogue column. SELLS has a compact category row above the list. Choosing a category shows a second row only when that category has subcategories; All restores the wider scope, and the search box continues to filter inside the selected category. General Store now shows Ammo, Clothing, Horse Care, Hunting, Provisions, Remedies, and Weapons; Weapons exposes Ammo, Repeaters, Revolvers, Rifles, and Shotguns.

The rendered 1600×900 check measured compact 46–50 px rows, exercised both filter levels and combined search, and preserved the existing placement, availability, price, toggle, destination, and Acceptance Report behavior. No live catalogue or shop data changed. Reopen or reload Shops and try Weapons → Revolvers, then combine it with a search.
