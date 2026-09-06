# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356483133 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/308

Created: 2026-08-30T19:39:40Z; updated: 2026-09-05T16:00:36Z

Exact metadata: [source record](sources/issue-5356483133-a66af9b1a6c80ed803bdcc0861f069b5acf3bf1381b988477480b8bb9db82ec9.json).

Menu changes: show unlearned GF abilities first and bright, learned abilities last and dim; group field magic into Attack / Restore / Indirect; add local clock display and battle-item ordering.

The earlier page-bound fix did not stop the crash. The captured crash came from a damaged font code in a generated flat-stat ability name. The name writer and existing names are now repaired and installed. Battle-item sorting now updates the separate battle ordering table. Other menu work remains open.

Check the crash repair:
- [ ] Open GF → Quezacotl → Learn Abilities, then go one page left. Confirm it stays open.
- [ ] Page both ways and confirm ability names and learned/unlearned states appear correctly.
- [ ] With Auto-sort Inventory enabled, open the battle Item menu with RB. Confirm usable items follow item-ID order and retain their quantities.


## issue 5356483133 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/308

Created: 2026-08-30T19:39:40Z; updated: 2026-09-06T12:59:27Z

Exact metadata: [source record](sources/issue-5356483133-2e42ef88a56caf863148fbf242dd69162f13a38e34af196751da199171c00f1c.json).

**Status: Partly repaired.** The generated-name crash and battle-item ordering repairs are recorded as installed; the broader menu work is unfinished.

Remaining scope includes the requested ability presentation, magic grouping and clock/order controls. Keep the crash check separate from full acceptance.

- [ ] For the installed crash repair, open GF → Quezacotl → Learn Abilities and page left, then both ways. Confirm no crash or damaged names. With Auto-sort Inventory on, check the battle Item menu’s order and quantities; report the failing step.

## issue 5356483133 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/308

Created: 2026-08-30T19:39:40Z; updated: 2026-09-06T12:59:27Z

Exact metadata: [source record](sources/issue-5356483133-892d799d212457abb03fc39b74b885bbc147836ba7ace3325f4afc2f9f0f2e08.json).

**Status: Partly repaired.** The generated-name crash and battle-item ordering repairs are recorded as installed; the broader menu work is unfinished.

Remaining scope includes the requested ability presentation, magic grouping and clock/order controls. Keep the crash check separate from full acceptance.

- [ ] For the installed crash repair, open GF → Quezacotl → Learn Abilities and page left, then both ways. Confirm no crash or damaged names. With Auto-sort Inventory on, check the battle Item menu’s order and quantities; report the failing step.

## comment 5550343912 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/308#issuecomment-5550343912

Created: 2026-08-30T20:30:55Z; updated: 2026-08-30T20:30:55Z

Exact metadata: [source record](sources/comment-5550343912-29846609db638644779b1d0b954441bfc0a4fe94f3f27fac05cb4a3d82615256.json).

Auto-sort Magic now has a verified native path: when the Magic menu opens, it calls FF8's own 0x004F0030 sorter with magsort.bin mode 1 (Attack / Restore / Indirect) for all eight character lists. Enhanced Ability Menu, In-game Time, and Battle Item auto-sort remain fail closed because no complete native cursor/renderer/battle_order paths are proved.

## comment 5550343925 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/308#issuecomment-5550343925

Created: 2026-08-31T04:15:18Z; updated: 2026-08-31T04:15:18Z

Exact metadata: [source record](sources/comment-5550343925-5318ba0f56dc2692ad690fc1cbe248bb474d9f9dbba9037072fffdc6d1ca827d.json).

Auto-sort Magic is now connected to the normal FF8 Tweaks save, validation, readback, and FFNx patch composition path. It defaults off and emits no bytes while disabled. The issue-local executable check, full settings composition check, and hidden rendered Tweaks check passed. Enhanced Ability Menu, In-game Time, and Battle Item auto-sort remain fail-closed pending proved engine paths, so this issue stays actionable.

## comment 5550343929 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/308#issuecomment-5550343929

Created: 2026-08-31T09:23:31Z; updated: 2026-08-31T09:23:31Z

Exact metadata: [source record](sources/comment-5550343929-1640df034a7e351a1687ee1ec81147e5bcad557021888dd925a2d60149451c5e.json).

Enhanced Ability Menu is now implemented and integrated. It moves complete eight-byte ability records to the end, keeps unfinished records first, and reverses only the normal text palette so unfinished abilities are bright and completed abilities are dim. The setting defaults off and uses the shared Save control. Auto-sort Magic remains integrated. The two conditional ideas stay absent as required: FF8 exposes no safe live clock renderer for In-game Time and no native battle-order auto-sort path. Static, combined-patch, and hidden rendered checks pass. Please test Enhanced Ability Menu and Auto-sort Magic in-game.


## comment 5550343939 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/308#issuecomment-5550343939

Created: 2026-09-05T06:39:43Z; updated: 2026-09-05T06:39:43Z

Exact metadata: [source record](sources/comment-5550343939-1c15b479fe4f71493600717d18d84e13424f2bcf8df8ee6b2757a0a9efc1f7eb.json).

New game-ending crash: open GF, enter Learn Abilities, then move one page backward. The supplied screenshot shows the FFNx crash dialog. This is a failed runtime result, not accepted menu behavior. Enhanced Ability Menu is a relevant path to examine, but the cause has not been established. At preservation time FFNx.log was empty; the screenshot and current configuration were preserved locally. Investigate previous-page wraparound and menu indexing before claiming this repaired. Work remains deferred under Lexer’s budget instruction; no game launch, debugging pass, or runtime/settings change was performed.

## comment 5550343949 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/308#issuecomment-5550343949

Created: 2026-09-05T06:51:09Z; updated: 2026-09-05T06:51:09Z

Exact metadata: [source record](sources/comment-5550343949-6077d5da7f134e7646f18a3defbb715d3f5e5c59839fbdb3a2b571115309c3ab.json).

Battle Item ordering remains unresolved. Lexer wants to organize items in the order actually shown during battle; the full Item menu order appears unrelated. The existing battle-sort requirement has not produced that control. Do not describe it as impossible without tracing the battle list and its mapping. Determine whether native rearrangement can control that order, then expose the actual battle order without corrupting inventory. Deferred; no new implementation or game test.
