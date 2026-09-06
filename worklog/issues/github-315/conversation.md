# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356484437 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315

Created: 2026-08-29T15:23:55Z; updated: 2026-09-05T13:53:43Z

Exact metadata: [source record](sources/issue-5356484437-d244e6268463d081f433a01cdeec6da9d654d12476e0eecc8c40a51b4448cb36.json).

Universal Item opens the battle Item menu with Look Right / RB. Enhanced Scan opens enemy targeting with Square / X, scans the chosen enemy without using stock or spending the turn, and lets you cancel.

Corrected Scan targeting and cancellation. Ready for an in-game check. Battle item ordering is tracked in #308.

Your check:
- [ ] Restart Lexeditor. Enable Universal Item and Enhanced Scan, save, and enter a battle with two enemies. On your turn, press Square / X. Confirm you can choose either enemy.
- [ ] Cancel targeting. Confirm the same character keeps their turn.
- [ ] Open it again and confirm a target. Confirm that enemy’s Scan information appears, Scan stock stays unchanged, and the same character can still act. Repeat once.
- [ ] Press RB. Confirm the normal Item menu opens and can be cancelled.


## issue 5356484437 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315

Created: 2026-08-29T15:23:55Z; updated: 2026-09-06T13:07:42Z

Exact metadata: [source record](sources/issue-5356484437-670f6b8aee5dcac3debf7f9e3e9aa07f85a053bdd8c5ced95a8daad8dc6a49db.json).

**Status: The latest Scan repair is ready for an in-game check.** A banner/animation alone is not a successful Scan.

- [ ] Restart Lexeditor, enable Enhanced Scan and Universal Item, save and enter a two-enemy battle. On your turn press Square/controller X: choose either enemy, cancel once, then reopen and confirm.
- [ ] Confirm the chosen enemy’s Scan information appears, stock is unchanged and the same character keeps their turn. Press RB/Look Right and confirm Item opens and cancels normally. Report the failed step.

## issue 5356484437 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315

Created: 2026-08-29T15:23:55Z; updated: 2026-09-06T13:07:42Z

Exact metadata: [source record](sources/issue-5356484437-a9a8bd141358f4c0b85c02baafe90be4af0bddb5348d67514ee4ff266c9b7e92.json).

**Status: The latest Scan repair is ready for an in-game check.** A banner/animation alone is not a successful Scan.

- [ ] Restart Lexeditor, enable Enhanced Scan and Universal Item, save and enter a two-enemy battle. On your turn press Square/controller X: choose either enemy, cancel once, then reopen and confirm.
- [ ] Confirm the chosen enemy’s Scan information appears, stock is unchanged and the same character keeps their turn. Press RB/Look Right and confirm Item opens and cancels normally. Report the failed step.

## comment 5550345293 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315#issuecomment-5550345293

Created: 2026-08-29T21:26:46Z; updated: 2026-08-29T21:26:46Z

Exact metadata: [source record](sources/comment-5550345293-1449daa89aa9c21f37acb2d04411bc7116496a3e78e410969e212178c3670fae.json).

Universal Item is implemented behind its Settings toggle. Look Right now uses FF8's configured action mapping, applies the native Item-disabled gate, and enters the native Item availability/dispatch path without adding a sixth command slot. Disabled mode emits no hook and keeps vanilla input handling. Scan remains actionable while its safe target-to-Scan-screen transition is traced; the known effect path would execute Scan and consume battle state, so it is not used as a shortcut.

## comment 5550345311 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315#issuecomment-5550345311

Created: 2026-08-29T22:03:53Z; updated: 2026-08-29T22:03:53Z

Exact metadata: [source record](sources/comment-5550345311-0863ca75df45db88aeb4b54383265eb0a2bf1e326e623ddba3a1057f64771b1b.json).

Previously-scanned Scan is now implemented behind its Settings toggle. Look Left requires exactly one selected enemy whose persisted Scan bit is already set, builds a read-only Scan target record, queues the normal Scan screen, and uses sentinel-owned completion so the actor is not marked complete and the turn should remain active. Unknown enemies do nothing. Universal Item remains implemented. The generated patch and adjacent settings tests pass; please confirm both shortcuts in battle.

## comment 5550345324 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315#issuecomment-5550345324

Created: 2026-08-30T19:39:12Z; updated: 2026-08-30T19:39:12Z

Exact metadata: [source record](sources/comment-5550345324-d6ff6912f0e3d6913f6582a3f1a04d6f0126c807aa01fea28052d8a46e388580.json).

Runtime result: the current Scan shortcut does not open Scan and interferes with overworld Look Left. Replace it with Enhanced Scan: during an actor turn, the right-stick action opens enemy target selection; confirming a target runs normal Scan without stock, without consuming Scan magic, and without consuming the turn. It must not remap or suppress field/world camera controls.

## comment 5550345338 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315#issuecomment-5550345338

Created: 2026-08-30T20:00:35Z; updated: 2026-08-30T20:00:35Z

Exact metadata: [source record](sources/comment-5550345338-6543dbcd6b998735669a0b6024aa0e3a326f86028368a6398ac955af30301dba.json).

I removed the old Scan hook. It captured Look Left outside battle and never had a proved target-selector-to-Scan return path. Universal Item remains independent. Enhanced Scan now emits no bytes and is disabled in Settings until the battle-only right-stick selector and no-turn Scan return are resolved.

## comment 5550345346 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315#issuecomment-5550345346

Created: 2026-08-30T20:44:26Z; updated: 2026-08-30T20:44:26Z

Exact metadata: [source record](sources/comment-5550345346-ac224293e7005c19d57f83c28f6569d38f49e16ab1947d2b8753924ae88d0e54.json).

Enhanced Scan now uses Card Game / Square (X on XInput), not R3. The battle-only router opens FF8's native enemy selector, marks only the confirmed Scan action, bypasses stock only for that action, and returns the same actor after Scan teardown. Universal Item remains on Look Right / RB. The installed generated patch contains no Look Left / LB hook.

## comment 5550345362 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315#issuecomment-5550345362

Created: 2026-08-31T05:36:26Z; updated: 2026-08-31T05:36:26Z

Exact metadata: [source record](sources/comment-5550345362-0ae3b87a7b2081d4574eba781711663a5516af57aeb5fcf559f79c504c2f41fe.json).

The target-confirm crash was caused by an incomplete command descriptor. It used Scan's spell target flags but omitted FF8's command-layer native-target bit, so confirmation entered Magic's submenu state without a selected spell and produced an empty target set. That matches the recorded crash at FF8 address 0x00502136.

Enhanced Scan now uses the verified direct target-controller branch. I also changed the verifier so the crashing descriptor cannot pass again, regenerated the active patch, and kept the issue in `waiting` for the real battle check. Please test open, cancel, and target confirmation; confirmation should show Scan, leave Scan stock unchanged, and return control to the same character without consuming the turn.

## comment 5550345376 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315#issuecomment-5550345376

Created: 2026-09-04T16:24:02Z; updated: 2026-09-04T16:24:02Z

Exact metadata: [source record](sources/comment-5550345376-1c4d328e093dbdf3373df1e9fc571f761ecd11df9008162016c4b1fa737cf213.json).

Enhanced Scan now uses FF8's native Magic action producer and queue lifecycle instead of rewriting a generic command record. Card Game / X opens the battle-only enemy selector; its private Scan entry bypasses inventory stock, cancel uses the native return path, and completion keeps the same actor's turn active. The old crashing descriptors are banned by the verifier. Static and composition checks pass. Please test open, cancel, and target confirmation in battle; confirmation must show Scan, leave Scan stock unchanged, and return to the same actor without spending the turn.

## comment 5550345391 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/315#issuecomment-5550345391

Created: 2026-09-05T06:51:10Z; updated: 2026-09-05T06:51:10Z

Exact metadata: [source record](sources/comment-5550345391-45559272f077125914c8b164b969a58b8e63dda2ad44460bf9e8cee2d4cfdf0e.json).

In-game Enhanced/Universal Scan check failed: pressing Square briefly opens a small Scan entry with a pointer beside the command menu, then it disappears. The actor animates and Scan appears at the top, but no target selection occurs and no enemy is scanned. Screenshot preserved locally. The command-name banner and animation do not prove a Scan result. Restore explicit target selection, cancel behavior, actual Scan output, unchanged stock, and retained turn. Deferred.
