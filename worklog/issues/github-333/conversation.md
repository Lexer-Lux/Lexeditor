# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356487639 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/333

Created: 2026-08-24T15:38:07Z; updated: 2026-09-05T07:40:31Z

Exact metadata: [source record](sources/issue-5356487639-03d5687360b22c0507e1e8c84a6d76acbc8bac78ed1412c1289bb9a2e5c2e989.json).

Slow game time while the RDR weapon radial menu is open. Add a setting for the time factor. Restore the prior game time scale when the radial closes or the ASI stops. Use a real radial-open state and a resolved RDR time-scale mechanism, not a guessed RDR2 native or an unrelated input hold.

Vertically center the weapon radial menu on screen. Use the actual RDR radial Flash/layout state or a proven archive-relative override. Do not move unrelated HUD surfaces.

Acceptance: opening the radial applies the configured factor, closing it restores normal time, changing the setting changes the observed factor, and the radial center aligns with the vertical screen center at multiple resolutions.

## issue 5356487639 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/333

Created: 2026-08-24T15:38:07Z; updated: 2026-09-06T12:38:42Z

Exact metadata: [source record](sources/issue-5356487639-66a18509ccefed71dae3b95cce35d33c97ae699bd719c69b80e4ddd681fc46eb.json).

The weapon wheel should use configurable slow motion and sit vertically centered.

**Status: Broken and deferred.** Opening it with Tab reproduced an access violation and left game/helper processes hanging. The cause is unconfirmed; neither slow motion nor centering is accepted.

No further game testing is requested until the crash is repaired. The earlier instruction to defer implementation/testing remains in force.

## issue 5356487639 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/333

Created: 2026-08-24T15:38:07Z; updated: 2026-09-06T12:38:42Z

Exact metadata: [source record](sources/issue-5356487639-cbbefb04352197a4d75794f2b1b111734fc4325c50e1f2f33a50ee586a736332.json).

The weapon wheel should use configurable slow motion and sit vertically centered.

**Status: Broken and deferred.** Opening it with Tab reproduced an access violation and left game/helper processes hanging. The cause is unconfirmed; neither slow motion nor centering is accepted.

No further game testing is requested until the crash is repaired. The earlier instruction to defer implementation/testing remains in force.

## comment 5550348971 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/333#issuecomment-5550348971

Created: 2026-08-27T05:50:35Z; updated: 2026-08-27T05:50:35Z

Exact metadata: [source record](sources/comment-5550348971-a71169645e377b0dcea6f9976712093a1baa3df7e428ffbe95cd07700f2b8cd6.json).

Runtime check failed: the weapon radial is still above or below the vertical screen center, and opening it does not slow game time.

## comment 5550348985 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/333#issuecomment-5550348985

Created: 2026-08-27T06:17:34Z; updated: 2026-08-27T06:17:34Z

Exact metadata: [source record](sources/comment-5550348985-ba646914e3df2ef33b0ef917529977bc0d363fa3443446a9bba5d8507cdaf2eb.json).

Installed the repaired development plug-in. Slow motion now waits for the engine to apply the configured 0.25 scale instead of undoing it in the same tick. The radial also uses the HUD movie center value and checks the coordinate write. Please confirm vertical centering, visible slowdown, and normal speed after the wheel closes.

## comment 5550348994 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/333#issuecomment-5550348994

Created: 2026-09-05T06:28:15Z; updated: 2026-09-05T06:28:15Z

Exact metadata: [source record](sources/comment-5550348994-69867756a3d22f702863a66000158ba7afbc5b3a2c42bbff5431000cfbfb6bfe.json).

The new report reproduces an access violation when Tab opens the weapon radial, followed by a process that does not finish closing. The last runtime log records a failed centering readback and a slow-motion request before it stops. Investigation is active; those logs do not identify the faulting instruction. A controlled game test is authorized.

## comment 5550349004 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/333#issuecomment-5550349004

Created: 2026-09-05T06:29:10Z; updated: 2026-09-05T06:29:10Z

Exact metadata: [source record](sources/comment-5550349004-e9695ddeee736075ea3cc9730726a8bcdbd513e94ecf7e0004f5fffb796fce07.json).

Deferred at Lexer’s request to limit further work. The authorized test reproduced the same crash when the radial opened. Both sessions ended after failed centering readback and time-scale apply/restore. The game and its error/helper processes remained alive. Logs are preserved locally; both INI files were unchanged. Root cause is still unconfirmed. Do not resume testing or implementation until Lexer asks.
