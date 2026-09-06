# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356484756 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317

Created: 2026-08-29T14:44:24Z; updated: 2026-09-05T07:39:48Z

Exact metadata: [source record](sources/issue-5356484756-ac2bcd53a7c11ee6781a36883443d32a87346e8762fdb0ada4684ba6128bcc16.json).

Add two functional FF8 gameplay settings:

- Monogamy: true/false, default false. When enabled, one character can have only one GF junctioned. A new second junction is refused. When gameplay enters a field or the world map, any character whose existing save data has several GFs junctioned has all of those GF junctions cleared. Removal and transfer remain available. Fixed Command Menu depends on Monogamy and cannot be enabled without it.
- Auto-sort Inventory on open: true/false, default false. When enabled, opening the in-game Item menu runs FF8's normal 198-slot compaction once before the untouched Item-menu initializer. It does not force a controller state or rewrite inventory order while the menu is closed.

Both settings require verified FFNx/Hext runtime hooks. The editor controls must save, reload, generate deterministic patches, and preserve vanilla behavior when disabled.

Player check:
1. On a test save, junction several GFs to one character. Enable Monogamy, save, and launch. Enter a field or the world map and confirm that character now has no GFs junctioned.
2. Junction one GF and confirm a second cannot be added. Confirm removal and transfer still work.
3. Disable Monogamy and confirm vanilla multi-GF junction behavior returns.
4. Enable auto-sort, scramble the inventory, close the Item menu, and reopen it. Confirm the normal game sort occurs once and the Item screen renders.
5. Disable auto-sort and confirm reopening the Item menu preserves the current order.

## issue 5356484756 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317

Created: 2026-08-29T14:44:24Z; updated: 2026-09-06T13:07:43Z

Exact metadata: [source record](sources/issue-5356484756-250b0dd5fc8715e87f5e508639444e2208c221bf966da22a4c67b732ea8b36a1.json).

**Status: Controls and patches are implemented; gameplay checks remain.** Use a copied save: Single GF intentionally clears a character’s existing multiple-GF junctions.

- [ ] Enable Single GF, save and launch the copied save. Enter a field: a character with several GFs should lose those junctions; after adding one, adding a second must be refused. Removal/transfer should still work.
- [ ] Disable it and relaunch: normal multi-GF junctioning should return.
- [ ] Enable Auto-sort Inventory, rearrange items and reopen Item: expect normal sorting. Disable it and confirm order is retained. Report the failed check; battle-item ordering is separate in #308.

## issue 5356484756 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317

Created: 2026-08-29T14:44:24Z; updated: 2026-09-06T13:07:43Z

Exact metadata: [source record](sources/issue-5356484756-c108979f2ae1256c55e0895cbf88b92ef9afc1ec87d7922c14d0eac8ea1d73cb.json).

**Status: Controls and patches are implemented; gameplay checks remain.** Use a copied save: Single GF intentionally clears a character’s existing multiple-GF junctions.

- [ ] Enable Single GF, save and launch the copied save. Enter a field: a character with several GFs should lose those junctions; after adding one, adding a second must be refused. Removal/transfer should still work.
- [ ] Disable it and relaunch: normal multi-GF junctioning should return.
- [ ] Enable Auto-sort Inventory, rearrange items and reopen Item: expect normal sorting. Disable it and confirm order is retained. Report the failed check; battle-item ordering is separate in #308.

## comment 5550345662 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345662

Created: 2026-08-29T15:04:10Z; updated: 2026-08-29T15:04:10Z

Exact metadata: [source record](sources/comment-5550345662-e5db6beb9344507a447d3ec03d69e4fbebeffd75001e1d35e251cab5722a1457.json).

Implemented both settings. Maximum GFs per Character is bounded to 1-16 and blocks only a new GF that would exceed the cap; it does not remove existing junctions. Auto-sort Inventory runs FF8's own Sort action once when the Item menu opens. Both controls save and reload, the generated patch checks the supported executable bytes, and the hidden rendered Settings view passed. Please restart Lexeditor, save a low GF cap and enable auto-sort, then use the two checks in the issue body in-game.

## comment 5550345671 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345671

Created: 2026-08-29T15:08:55Z; updated: 2026-08-29T15:08:55Z

Exact metadata: [source record](sources/comment-5550345671-31289c9a84b691a82e2c1d1e1d6db1caafeb5455e5cf2c53ff6978a3d6561c35.json).

Correction before player testing: a full character-structure audit showed that the first GF-cap hook targeted the character status tail, not the GF mask. I removed that hook from generated patches and restored this issue to actionable. Default settings and inventory auto-sort remain safe; Lexeditor now refuses to generate a non-vanilla GF cap until the real junction-write path is patched.

## comment 5550345680 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345680

Created: 2026-08-29T15:23:14Z; updated: 2026-08-29T15:23:14Z

Exact metadata: [source record](sources/comment-5550345680-e692a0e1c8adb7fa1336a1399989930215a018fd291b22ea74856ab5efd13083.json).

I removed the Maximum GFs per Character control instead of leaving a setting that cannot work. The invalid hook, saved key, API fields, and UI row are gone. Auto-sort Inventory remains because its native Item-menu path is independently verified. The GF limit will return only after the real GF-mask write boundary is verified.

## comment 5550345694 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345694

Created: 2026-08-29T15:39:46Z; updated: 2026-08-29T15:39:46Z

Exact metadata: [source record](sources/comment-5550345694-2d7c20138f3177707e72003c608ed3e1691c7f4d03ab1a1cd79eb94321faeca7.json).

The GF limit is restored with the correct hook. It now runs only when the Junction menu is about to add a new bit to the selected character's proposed GF mask. Existing junctions, removals, transfers, character-record swaps, and the later save-data commit remain vanilla. Restart Lexeditor, set Maximum GFs per Character to 1, save, then launch FF8: junction one GF, confirm a second cannot be added, confirm the first can still be removed, and confirm it can be transferred to another character. Auto-sort remains independent.

## comment 5550345714 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345714

Created: 2026-08-29T19:11:33Z; updated: 2026-08-29T19:11:33Z

Exact metadata: [source record](sources/comment-5550345714-01bb045442ee8bfc3b0f0ff57ff4a460e8b9d142ce49be14287b34e92de27a90.json).

The duplicate labels had no separate meaning. The active Settings tab, the `Gameplay settings` toolbar, and the inner `SETTINGS` heading all named the same page.

I removed both internal headings and the now-empty toolbar row. Settings opens directly into the controls. The hidden render confirms one page label, all three controls, and no errors.

## comment 5550345727 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345727

Created: 2026-08-29T21:15:46Z; updated: 2026-08-29T21:15:46Z

Exact metadata: [source record](sources/comment-5550345727-fc133b3dd91a6f56abf370f2e535b9f727b929b838d319ba49fe5a36f7a84135.json).

Maximum GFs is now the Single GF checkbox. When enabled, the verified junction-add gate refuses a different second GF but leaves the existing GF, removals, and transfers alone. Fixed Command Menu is also blocked unless Single GF is enabled. Auto-sort remains independent. Save/readback, generated-patch guards, mutation checks, and the rendered Settings page pass; the remaining check is the in-game one-GF add/remove/transfer behavior.

## comment 5550345735 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345735

Created: 2026-08-30T19:22:59Z; updated: 2026-08-30T19:22:59Z

Exact metadata: [source record](sources/comment-5550345735-f8bbf1fd7299e1d82d078a06445e07815226ae8d823d64b015ec8e2277af95f7.json).

The existing-save bypass is now handled. With Single GF enabled, each field or world-map entry checks all eight character GF masks. A mask with several GFs is cleared completely; empty and one-GF masks stay unchanged. The Settings warning now states this consequence. Static byte, stride, and normalization checks pass. Please use the first player check in the revised issue body on a backup or test save; this cleanup is not yet player-confirmed.

## comment 5550345750 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345750

Created: 2026-08-30T19:39:08Z; updated: 2026-08-30T19:39:08Z

Exact metadata: [source record](sources/comment-5550345750-06aaf2ea87667a771b5e469154c142cb1c8252c696f7be5c9b21950dca28e67b.json).

Runtime regression: enabling Auto-sort Inventory makes the in-game Item screen black. This is now actionable again. The same Settings repair will rename Single GF to Monogamy and correct checkbox alignment; the underlying saved key can remain compatible.

## comment 5550345766 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345766

Created: 2026-08-30T19:59:04Z; updated: 2026-08-30T19:59:04Z

Exact metadata: [source record](sources/comment-5550345766-94db53b69e5c8dc0e88438b2453526d18cdec04b61343fb4a7ddaef22e263613.json).

The black Item screen came from the auto-sort hook forcing Item controller state 79 before startup states 0–2 completed. I removed that state jump. The replacement applies FF8's own 198-slot compaction before the untouched Item initializer, so the normal screen startup still runs. Static and generated-patch checks pass; the repaired option still needs an in-game check.

## comment 5550345770 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345770

Created: 2026-08-31T01:48:37Z; updated: 2026-08-31T01:48:37Z

Exact metadata: [source record](sources/comment-5550345770-92ffee9ce2d4ac0df0bdc8365b5d6ba3278f3eae66e4cf5a5e999ba08cbe031d.json).

Tweaks are now mod data only. A new FF8 mod resets every Tweak switch to off and writes a no-hook gameplay patch, while existing mods keep their own saved switches and values. Flying EVA now has a separate enabled switch, so keeping 25 in its value box does not activate it. The rendered fresh-mod check showed no Lexer default controls and all switches off.

## comment 5550345776 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/317#issuecomment-5550345776

Created: 2026-08-31T05:06:11Z; updated: 2026-08-31T05:06:11Z

Exact metadata: [source record](sources/comment-5550345776-da9a4e24944f3f0031d9322ddff390eb8fa80dd5900b8559f3cdeec559b8e3e7.json).

Tweaks no longer has a second save button. Tweak edits now use only the normal top-bar Save/Discard transaction with the rest of the selected mod. The rendered check confirmed the local control is absent and the global Save becomes active after a Tweak edit.
