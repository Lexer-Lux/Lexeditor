# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5285594217 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21

Created: 2026-08-29T08:49:48Z; updated: 2026-09-05T06:34:47Z

Exact metadata: [source record](sources/issue-5285594217-99c346f43d2703c106f5e15328443c7e7337be9e4c1051fd1fea121424f12b4e.json).

Add the installed 2013 Steam release of Final Fantasy VIII to the shared Lexeditor host. Use the common list-detail, paging, save/undo, Data Map, and game-status systems. Prepare a private extracted baseline from the real FS/FI/FL archives and save gameplay edits through a safe FFNx-compatible override project, never by silently overwriting the installed archives. Initial editable coverage should prioritize the high-impact gameplay data: items and prices, shops, weapons and upgrade recipes, magic, Guardian Forces and abilities, starting data, and enemy stats where the format is proven. Use bounded controls and named choices from the game schema. Show exact partial/not-integrated status for field scripts, encounters, models, textures, audio, and other formats that are not yet writable. Reuse the maintained FF8 Ultimate Editor formats and FFNx direct-mode contract with their required source and license records.

## issue 5285594217 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21

Created: 2026-08-29T08:49:48Z; updated: 2026-09-06T12:45:14Z

Exact metadata: [source record](sources/issue-5285594217-b35595b5aeec6f8a7b80a534d71b7e6524b9711a0560e4ca52fc462b1892f5b7.json).

The FF8 editor exists; this is no longer an unstarted plugin request. Editing, startup and some save-loading paths work, but complete gameplay acceptance remains outstanding.

**Work remains:** finish the missing runtime/features in #31, #84, #91, #93, #100 and #308–#328, then prepare concrete checks for Draw, Refine recipes and text overrides. Do not mark the whole plugin ready because individual tabs or patches exist.

## comment 5461473582 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5461473582

Created: 2026-08-29T09:09:34Z; updated: 2026-08-29T09:09:34Z

Exact metadata: [source record](sources/comment-5461473582-9b5ce062ae7612b3b7920e01cb81ef6b7722d62abadac36549649799c1e6b4c0.json).

Implemented the first functional FF8 (2013 Steam) plugin. It uses the shared Lexeditor window and list-detail view, reads the installed English archives, and keeps a private extracted baseline. Items, shops, weapon upgrade recipes, Magic, and GFs are editable; saves go to C:\FF8Mod\direct and do not change the Steam archives. Enemies are inventoried but remain read-only, and the Data Map identifies the other partial or unsupported files. Restart Lexeditor, open Final Fantasy VIII, and check those five editable views. FFNx is not installed in the current FF8 directory, so the game will not load the override project until that runtime step is complete.

## comment 5461495377 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5461495377

Created: 2026-08-29T09:14:54Z; updated: 2026-08-29T09:14:54Z

Exact metadata: [source record](sources/comment-5461495377-a618e7adc3a613dde1c05782d095966705f02b03413b058a7ff466a46fff9894.json).

Added the requested Characters tab and reordered the core tabs to Items, GFs, Characters, Magic, and Enemies. Shops, Weapons, and Setup remain after them because this was a partial tab list. Characters edits the 11 named kernel records, including EXP, limit/crisis behavior, gender, and stat-growth coefficients. The character save/readback check passed without changing the extracted baseline.

## comment 5461542202 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5461542202

Created: 2026-08-29T09:26:21Z; updated: 2026-08-29T09:26:21Z

Exact metadata: [source record](sources/comment-5461542202-a176429dc9403781e1b8e068dbadde986f37b340bb8a4eff92c9efb169ee216f.json).

Rebuilt the FF8 plugin around the original menu style instead of the generic blue JRPG theme. It now uses black negative space, gray beveled panels, compact black group labels, and a private browser font generated from the installed game's sysfnt.TEX and sysfnt.tdw files. The font is not bundled or redistributed. Items and Characters both passed rendered checks at 1600 x 1000, and the existing save/readback checks still pass. Restart Lexeditor and inspect the FF8 tabs; FFNx is still the separate requirement for loading saved overrides in-game.

## comment 5461865916 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5461865916

Created: 2026-08-29T10:42:44Z; updated: 2026-08-29T10:42:44Z

Exact metadata: [source record](sources/comment-5461865916-06f47e379f87448378638c61bf9a318831855545b922337de98a5ae56a1372a5.json).

FF8 now uses the shared list-detail behavior for complete fitted rows, same-line title IDs, alphabetical tabs, and right-edge pager ranges. Shops can remove stock, reuse freed slots to add stock, and explain that Rare stock is gated by Tonberry's Familiar menu ability. Integrated item, shop, weapon, Magic, GF, and Character fields now show clickable vanilla values; element and supported status labels use icons generated from this installation's icon.sp1/icon.TEX.

## comment 5472349081 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5472349081

Created: 2026-08-31T00:47:56Z; updated: 2026-08-31T00:47:56Z

Exact metadata: [source record](sources/comment-5472349081-5bea4bd3de92dc0847380b36ba40c2a89fc2c507cec0f93bc798b3d107f60058.json).

Cause: the shared no-action detail heading placed the identity block in its rightmost auto-width grid column, and FF8 still had a late rule that forced gray caption backgrounds. The shared grid now spans the identity across the free width, and FF8 section captions are transparent with no shadow. A 1600 x 1000 Items render confirms the item name starts after its icon, the ID stays right-aligned, both visible captions are clear, and there is no horizontal overflow. Please check any item in FF8 Items.

## comment 5472415511 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5472415511

Created: 2026-08-31T00:59:48Z; updated: 2026-08-31T00:59:48Z

Exact metadata: [source record](sources/comment-5472415511-6cb3c3e374b384c5f09a84dacbe390eb33f4c34c284d209f6e060c14092243f9.json).

Repaired the shared control geometry used by FF8 Encounters. Editable inputs now fill their table track, header help markers take normal layout space beside the label, and reference-aware pins use the live field's own reference rail instead of drifting into the property name. A 1600 x 900 FF8 render showed complete X/Y/Z values, no header overlaps, and the Stage ID pin at the input's top-right edge. The shared Detail and live-reference checks also pass.

## comment 5476963613 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5476963613

Created: 2026-08-31T10:21:17Z; updated: 2026-08-31T10:21:17Z

Exact metadata: [source record](sources/comment-5476963613-fe439067c9236fa6c22e932971a72052dbcef4f5d5ef74e6411bc93814d56c23.json).

Completed the remaining initial FF8 plugin coverage for starting data. The new Starting Data tab edits party/progress and config fields, all 16 GFs, all eight characters, 32 Magic slots per character, and all 198 inventory slots. Saves use the FFNx project and preserve every unnamed source byte. Binary boundary checks, temporary save/readback, the full FF8 smoke test, and hidden renders of all four subtabs passed. Please restart Lexeditor, inspect Starting Data, save a small change, and confirm it in game.

## comment 5482423327 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5482423327

Created: 2026-08-31T18:04:59Z; updated: 2026-08-31T18:04:59Z

Exact metadata: [source record](sources/comment-5482423327-1558d6d2399a1ce5da679540ec628aaadd87bb0a977b59c239421ab73af96d87.json).

Completed this FF8 UI repair pass across Characters, Encounters, Items, Magic, Shops, and Weapons. Character fields and graphs use the full panel; encounter coordinates are centered and enemy names support both record navigation and Finder; item prices and flags no longer overflow; Magic composite rows are named and horizontal; Shop headings keep their right inset; and Weapon controls use one responsive grid. The complete FF8 rendered suite plus Enemies, Weapons, Shops, and live-reference checks pass.

## comment 5538726173 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5538726173

Created: 2026-09-04T09:49:18Z; updated: 2026-09-04T09:49:18Z

Exact metadata: [source record](sources/comment-5538726173-7004010ca63f7b00fefb825e1dfd3c9452cb0dd59094750d087d36fa3a0aab5a.json).

Field map IDs must use the shared styled ID-field treatment. Refine must fill its panel width with no black strip on the right. Keep the current one-row-per-recipe layout, but remove the redundant DISPLAYED TEXT label beside the RECIPE TEXT control.

## comment 5539027676 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5539027676

Created: 2026-09-04T10:16:46Z; updated: 2026-09-04T10:16:46Z

Exact metadata: [source record](sources/comment-5539027676-a0b5fbc11d37f9314b9dee6cedff4478e0f28db5a545988d9f4a48e9165ab594.json).

Current FF8 regressions: the Field right panel rapidly loses and restores its lower half; dragging Accelerator price from 50,000 to the right lowers it to about 33,000; and the Text list clips both sides of Description. Fix the field layout instability, correct slider direction and range mapping, and enforce fitted labels plus panel minimum widths.

## comment 5539181038 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5539181038

Created: 2026-09-04T10:31:23Z; updated: 2026-09-04T10:31:23Z

Exact metadata: [source record](sources/comment-5539181038-b7d323375ce88c6cfcfffc5e9c660d4b39ae3014108708e07ac66e0bb1640535.json).

Field map IDs now use the shared styled ID cells. Refine fills the available width, and RECIPE TEXT no longer repeats a DISPLAYED TEXT label. The Refine binary, Save/readback, and rendered layout checks pass. Other FF8 reports on this issue remain actionable.

## comment 5539252711 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5539252711

Created: 2026-09-04T10:38:36Z; updated: 2026-09-04T10:38:36Z

Exact metadata: [source record](sources/comment-5539252711-c07b5b7b63b18a73608e43f6c8f77a4590819da32819812ef1bd557698ec59d8.json).

Feature freeze for triage. New FF8 data-view reports:

- In Text, show the field name in the Detail header subtitle instead of appending it to the record name.
- Rename Starting Data to Start.
- Treat slot columns as ID columns. The slot column in Items detail currently does not use that shared presentation.

Do not implement these changes until Lexer triages them.

## comment 5540709078 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5540709078

Created: 2026-09-04T12:53:20Z; updated: 2026-09-04T12:53:20Z

Exact metadata: [source record](sources/comment-5540709078-94b517624448284fa2a5271a3d701f8e90c83627e9c71e0dbed37ae06dc07570.json).

Cause found and corrected: ordinary Save silently changed an enabled Shared Magic request back to false whenever runtime readiness had not yet been established. The selected mod, active runtime file, and every launch log therefore showed `requested=0`, so FFNx installed no Shared Magic hooks. Save now preserves the mod's choice and leaves installation/verification to the launch step. I restored the current mod and composed runtime to `sharedMagicInventory = true`; the installed derivative and packaged driver have the same verified hash. The remaining check is a fresh game launch: the Shared Magic log must show `requested=1`, 28 function hooks, four call-site patches, and active shared stock.

## comment 5540849246 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5540849246

Created: 2026-09-04T13:05:29Z; updated: 2026-09-04T13:05:29Z

Exact metadata: [source record](sources/comment-5540849246-e13e58b896c6ba3d8fb7a370deede888aaa7812c5bcbbf156f34b67c476fe834.json).

FF8 crashed at startup after several unaccepted gameplay Tweaks were enabled together. The current log reached MODE_MAIN_MENU and then faulted at 0x0045C947; Fast Start was present and had skipped the normal transition into that menu. I removed every gameplay hook without a successful in-game result from the selectable Tweaks page and added a server-side fail-closed gate, so old mod files and stale editor pages cannot reactivate them. Only Monogamy and Universal Item remain selectable because those are the two previously confirmed in game. The active mod and composed runtime were reset to the safe state, all FFNx XP/HP/targeting switches are off, Shared Magic is off, and the clean launch barrier passes. The quarantined implementations remain actionable and must be repaired and tested one at a time before they return.

## comment 5541163528 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5541163528

Created: 2026-09-04T13:31:26Z; updated: 2026-09-04T13:31:26Z

Exact metadata: [source record](sources/comment-5541163528-474b30bb167233d4cfd170f44e4818393a746e4e974f111e19853f3ffd4424e0.json).

The first repair batch is now available. Fast Start no longer replaces the opening callback set; it completes the native credits state and reached the main menu without the old crash. Auto-sort Inventory now applies the game's exact inventory transform before the untouched Item initializer, so the controller-state path that produced the black screen is gone. Shared Magic no longer has the circular install gate or silently saves itself as off: an isolated launch reported `requested=1`, 28 function hooks, four call-site hooks, heartbeats, and reached the main menu.

After restarting Lexeditor, Tweaks shows Monogamy, Fast Start, Auto-sort Inventory, Universal Item, and Shared Party Magic Inventory. They remain off by default. The remaining Shared Magic check is player-visible: load a save, confirm one party stock in the menu, then Draw, cast, transfer, inspect a junction stat, and save/reload. Auto-sort Inventory still needs one Item-screen check.

## comment 5541267645 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5541267645

Created: 2026-09-04T13:39:25Z; updated: 2026-09-04T13:39:25Z

Exact metadata: [source record](sources/comment-5541267645-c3bd38b30bbcb6a521e323807143e465d3737dcc5f22c7e203ff8b9ee073bd9b.json).

The rest of the completed replacement set is restored and remains off by default: Auto-sort Magic, Enhanced Ability Menu, Flying EVA, Party Switch, Draw Once, Streamlined Draw, Better Card, Command Menu Rework, True ATB Wait, Modern Controls, Vibration Rationalization, Better Targeting, Remove Damage Limit, XP Bars, and HP Bars. I enabled all restored Hext components and the three FFNx options together in a private runtime; FF8 loaded the combined patch and reached the main menu without an exception. Every feature contract and the 20-control rendered Tweaks check passes, and the current mod remains all-off.

Two controls remain unavailable rather than shipping known-bad code. Enhanced Scan's two synthetic action lifecycles both crashed after target confirmation; it needs a native Scan action path. Formulae Rework has only two of its five requested runtime formula paths, and the remaining formula decisions are not defined. Those remain actionable.

## comment 5541499221 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5541499221

Created: 2026-09-04T13:58:08Z; updated: 2026-09-04T13:58:08Z

Exact metadata: [source record](sources/comment-5541499221-2c62ca1705e575e3625057323cc542962c5351e280adb5762a5d24318c19e16b.json).

Command Menu Rework is intentionally dependent on Monogamy because its fourth command slot comes from the character's one junctioned GF. Your saved mod already has Monogamy on. The current rendered control can now be enabled, saved, disabled with Monogamy, and restored when Monogamy returns; both persistence and command-patch checks pass. Restart Lexeditor because the running host can still contain the older unbound Tweaks page.

## comment 5541572049 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5541572049

Created: 2026-09-04T14:04:06Z; updated: 2026-09-04T14:04:06Z

Exact metadata: [source record](sources/comment-5541572049-a24795c7317c825e8114a3b123daeb206b5b6f0d69985334be6126d1baf5e32d.json).

The new crash report identified a real release blocker. Windows recorded an access violation inside Lexeditor's `AF3DN.P` at save-load completion, while the selected mod had the whole unaccepted gameplay batch enabled. The three permanent rectangles also match the enabled experimental XP/HP drawing gates.

I quarantined every gameplay hook that has not passed a player-visible in-game check. Only Monogamy and Universal Item remain selectable. I reset the active mod and Shared Magic configuration, disabled the three FFNx drawing/targeting gates, regenerated the active Hext patch, and restored the verified stock FFNx 1.24.3 driver. The crashing derivative is preserved under a quarantine filename for diagnosis.

Restart Lexeditor before testing. Then launch FF8 and load a save. The acceptance check is: no three bar outlines, and the save reaches gameplay without freezing or crashing.

## comment 5541990259 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5541990259

Created: 2026-09-04T14:35:11Z; updated: 2026-09-04T14:35:11Z

Exact metadata: [source record](sources/comment-5541990259-7cf307d63257982f5fa5fbce3561d8d371dd4b4445fdc33cb8ca6d949b5c629d.json).

Correction: reducing Tweaks to two controls was containment, not a fix, and it was the wrong endpoint. The save-load crash is now traced from the full dump: Shared Magic cleared an FF8 dialog before releasing its warning state, FF8 synchronously re-entered the handler, and the same 100-byte frame repeated 9,912 times until the 1 MB stack failed. The repaired driver releases state before the FF8 call; a regression mutation restores the old order and must fail. The rebuilt driver is installed with Shared Magic enabled and completed a responsive startup with all hooks active and fresh heartbeats. A loaded-save check is still required, so this issue remains actionable while the remaining Tweaks are repaired rather than hidden.

## comment 5542456989 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5542456989

Created: 2026-09-04T15:08:10Z; updated: 2026-09-04T15:08:10Z

Exact metadata: [source record](sources/comment-5542456989-55f92e40e84781dff4830ba3cd75fd1ce9a9487d1e570a8de97cb7f62d11ccd7.json).

The save-load crash is now confirmed fixed. The first repair stopped the recursive crash, but a blocked Shared Magic migration still retained FF8's load controller after detecting more than 100 combined copies of one spell. That caused the permanent `Loading data` screen. The runtime now preserves all private spell stocks, disables Shared Magic for that session, and returns to the original loader without opening a warning. Lexer loaded the same save successfully, and the three main-menu rectangles remain gone.

Modern Controls was reset to off during containment, so the current missing right-stick camera movement did not exercise its hook. That setting remains part of the active Tweaks repair instead of being treated as a passed result.

## comment 5549883095 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5549883095

Created: 2026-09-05T06:10:04Z; updated: 2026-09-05T06:10:04Z

Exact metadata: [source record](sources/comment-5549883095-9e881494a023c963b6cff6b687910a84c60f8a310c65254862f236a772ab2d67.json).

Magic Compatibility and the Enemies Stats/AI/Battle Text panel now sit at the far left. The record list is in the middle and details stay on the right; choosing another record updates both panels. Compatibility also fits all 16 GFs. Main tab names now show in full, and Starting Data is named Start.

I also found that Targetable was still wider than its column despite the earlier check passing. Its column now has enough room, as does Loaded. Hidden checks passed at two window sizes, including Description placement and the type-text hover changing to ?. Reopen FF8 in Lexeditor to inspect these changes.

## comment 5549928151 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5549928151

Created: 2026-09-05T06:18:54Z; updated: 2026-09-05T06:18:54Z

Exact metadata: [source record](sources/comment-5549928151-740fa964f46b8909e06ac40b88e115e79e67f0bb2cb8634a3e648546b626ac6d.json).

FF8 graphs now show stacked fractions, raised powers and proper mathematical brackets. The start and end values use the same font and color as the equation. Long equations wrap at safe breaks, and values move clear of the equation when they would overlap. The existing game equations remain unchanged.

Rendered checks passed for Characters, GFs and Enemies at both 1600 and 1280 pixels wide, including variable highlighting and no clipped or overlapping equation text. Reopen FF8 in Lexeditor to inspect those graphs. The wider repairs on this issue remain actionable.


## comment 5549972401 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5549972401

Created: 2026-09-05T06:27:53Z; updated: 2026-09-05T06:27:53Z

Exact metadata: [source record](sources/comment-5549972401-bbe7aea4acada7bae07439d63d13b66088ff47235ceac131815595b58f855f7f.json).

The inset rectangle came from the toolbar drawing a padded surface around the subtab bar. The bar now owns one raised FF8 metal panel, with unboxed labels. Hidden checks and screenshots passed for Abilities, Refine and Enemies at both 1600 and 1280 pixels wide.

## comment 5550008248 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/21#issuecomment-5550008248

Created: 2026-09-05T06:34:47Z; updated: 2026-09-05T06:34:47Z

Exact metadata: [source record](sources/comment-5550008248-96ca1655abbc9e756433bc889e51796e0e187ee9f80f5900f2d9eae7aaa30e11.json).

The old GOAL.md handoff is retired. Remaining work is tracked here, not in a second local task list. Existing issues were reused; no implementation was resumed.

| Remaining work | Owning issue |
|---|---|
| Enhanced Scan: open/cancel/confirm, no stock or turn use | Lexer-Lux/LexersModForFF8#14 |
| Fast Start: game check | Lexer-Lux/LexersModForFF8#1 |
| Better Targeting: battle visibility | Lexer-Lux/LexersModForFF8#6 |
| Better Card / damage limit: battle checks | Lexer-Lux/LexersModForFF8#24, Lexer-Lux/LexersModForFF8#25 |
| Shared Magic: safe activation/migration | Lexer-Lux/LexersModForFF8#9 |
| Modern Controls: disabled after failure | Lexer-Lux/LexersModForFF8#5 |
| Party Switch: incomplete actor replacement | Lexer-Lux/LexersModForFF8#12 |
| Quistis retaining Treatment | Lexer-Lux/LexersModForFF8#11 |
| Flare item: specification | Lexer-Lux/LexersModForFF8#26 |
| Formulae Rework: missing rules and game checks | #31 |
| Field/world coverage and AI/battle-text checks | #84, #39 |
| Max Spell / Flat Stat game checks | #94, #92 |
| Cards: fixed-slot editor built; extra slots unresolved | #91 |
| GF spellbooks: deferred, no runtime patch installed | #93 |
| Ordered loader, conditional assets, featured release checks | #100 |

This issue retains the remaining shared plugin acceptance: Streamlined Draw with zero/one/multiple available spells and full-stock targets; HP/XP bars placement, animation, scaling and flicker; representative recipes from all five Refine tables; and actual loading of menu/kernel/executable text overrides. These are code-built claims awaiting the stated game results, not completed acceptance.

The handoff was stale: Cards editing and field backgrounds have since gained implementations, and startup/save loading was confirmed. That does not prove the other battle or asset checks. Historical technical notes were archived locally before deleting the handoff. Existing unrelated labels and issue states are preserved.
