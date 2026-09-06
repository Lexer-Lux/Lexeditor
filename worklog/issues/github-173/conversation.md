# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356300510 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/173

Created: 2026-08-06T03:19:37Z; updated: 2026-09-05T06:58:44Z

Exact metadata: [source record](sources/issue-5356300510-bc710b7ee6d7e41b8310890eafb7d878a5be7ced4f4e7fe985bddad139dc571d.json).

A recurring full-screen fade/haze still appears during ordinary gameplay. It resembles the exhausted/core-state visual treatment and has survived multiple attempted fixes.

This is a major visual regression.

Acceptance:
- No recurring exhaustion-like fade, haze, pulse, desaturation, or vignette during ordinary gameplay.
- Identify and remove the actual mod-owned trigger rather than masking the symptom with another timing threshold.
- Preserve intentional Rockstar fades for death, sleep, fast travel, missions, menus, intoxication, poisoning, temperature, and other legitimate states.
- Verify all mod-owned core writes/state transitions no longer fight the engine or repeatedly retrigger a core-state effect.
- Build and install for in-game confirmation.

## issue 5356300510 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/173

Created: 2026-08-06T03:19:37Z; updated: 2026-09-06T13:17:20Z

Exact metadata: [source record](sources/issue-5356300510-ac3a6555dbfd916e69b825d7e0e5575a514587d2ae9cee5d8eac0fcc33c99609.json).

**Status: Closed after the unwanted effect was removed.** The dropped CoreVignetteRamp plugin had remained installed and was being reinstalled automatically. Its loader files and reinstall path were removed; ordinary intentional game fades were not the target.

## comment 5550128754 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/173#issuecomment-5550128754

Created: 2026-08-06T03:24:17Z; updated: 2026-08-06T03:24:17Z

Exact metadata: [source record](sources/comment-5550128754-efa60bc2b2655a4e93941ef21663bc91d629acb1d533cccba2a8063156ded8d9.json).

Root cause confirmed from the current live session: the rejected standalone `CoreVignetteRamp.asi` is still installed and active. Its live log shows `running=1` almost continuously, with Stamina effect strength around 0.63–0.96 and Dead Eye around 0.72—the exact exhaustion-like pulsing haze. This survived earlier fixes because `Install-When-RDR2-Closes.ps1` kept reinstalling the dropped ASI on every deployment despite `CODEX.txt` explicitly saying never to reinstall it.

Fixed deployment:
- Removed the CoreVignetteRamp install calls.
- The installer now moves any game-root `CoreVignetteRamp.asi`/`.ini` into `mod storage/CoreVignetteRamp` after RDR2 exits.
- Added `[General] Enabled=0` to the current game-root INI as a defensive disable.
- Replaced the already-running stale deferred installer with the corrected watcher so it cannot resurrect the ASI again.

RDR2 currently has the ASI loaded, so complete removal takes effect on the next full restart. Keeping `actionable` until the watcher physically moves it and verifies the loader path is clean.

## comment 5550128778 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/173#issuecomment-5550128778

Created: 2026-08-06T05:47:17Z; updated: 2026-08-06T05:47:17Z

Exact metadata: [source record](sources/comment-5550128778-1ad7b65f16c21990de679e5003bc37b33cf309f378ca1b1d0717e5ad9d16532f.json).

Verified against the current running session: CoreVignetteRamp.asi/.ini are absent from the loader root and stored under mod storage; its log did not renew after restart, GameplayTweaks reserve logging is active, and the repo/installer contain no remaining fade trigger. Moving this to test me for visual confirmation that the recurring haze is gone.
