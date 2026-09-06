# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356286656 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/113

Created: 2026-08-06T01:45:22Z; updated: 2026-09-05T06:55:26Z

Exact metadata: [source record](sources/issue-5356286656-1806416d5341c4c50d632ba5468305983597a17dd5ff4f2541184df4143753fc.json).

## Confirmed system structure

RDR2 does not have one universal stealth percentage. It combines perception-profile data, authored Story detection helpers, LOS, player noise, witness/crime logic, and separate AI state machines.

A common hostile-detection helper is present across the decompiled Story scripts. In the configured `gang1.c` instance:

- Immediate visual detection uses a 30 m base distance and rejects the player beyond 35 m. It requires perception-area qualification and `CAN_PED_SEE_ENTITY(...) == 1`.
- A timed visual branch qualifies within 15 m for 1000 ms. Below 3.5 m, it can complete after 500 ms.
- The noise branch requires engine stealth noise above 4 plus an unresolved player-to-observer native. Crouch or cover changes that native's stance flag. Configured suppressions can block the result in cover or crouch. A separate stealth-state branch tests noise above 8.
- A lantern or torch has an explicit fallback at 5 m or less during the helper's 20:20–05:20 night window. It also requires the player to face the observer within 110 degrees and requires clear LOS.

These are common Story-script rules, not one universal engine rule. Law, witnesses, animals, and individual missions can use different logic or thresholds.

## Runtime evidence retained

The earlier completed neutral-observer runs established supporting inputs:

- `IS_TARGET_PED_IN_PERCEPTION_AREA` changed with distance, facing, and per-ped seeing range. It did not expose an accumulating awareness value.
- Crouch and stealth movement are separate states.
- Median player speed / engine stealth noise was `0 / 0` standing still, `0 / 0` crouched still, `1.365 / 0` crouch-walking, `1.333 / 1.827` walking, `3.955 / 5` running, and `5.616 / 10` sprinting.
- Drawing a weapon caused no response. Aiming caused a neutral observer to flee after about 526 ms. That was a threat reaction, not a hostile awareness meter.

The partial run `StealthProbe-20260809-232527.csv` completed steps 0–24 and began step 25 before abort. It corroborated the movement/noise tiers. Its first run/sprint instructions were swapped, but the measured states identify them: the faster input had noise 10 and the slower input had noise 5. These trials will not be repeated.

The partial run did not supply hostile-detection results. Its isolated guard did not execute the authored Story detection state machine, and the visual trials had the observer turned about 180 degrees away. The sound-only geometry was also uncontrolled. The cover step lacked a ready gate, and the lantern-off step was partial while the automatic belt lantern was still on.

## Short follow-up still needed

The replacement follow-up contains only seven conditions: solid cover hidden/exposed, lantern off/on at night, and clear/rain/fog. Every manual condition waits without sampling until F9 confirms it is ready. The CSV records the exact inputs used by `gang1.c` `func_2459`, including the three-state `CAN_PED_SEE_ENTITY` result and the immediate/lantern branch outcomes.

Issue Lexer-Lux/Lexeditor#105 must first restore manual lantern control. The audit remains `needs a human` until this short follow-up is completed and analyzed.

Canonical technical audit: `codex/stealth-perception.md`  
Attempt evidence: `worklog/issues/github-13.md`

## issue 5356286656 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/113

Created: 2026-08-06T01:45:22Z; updated: 2026-09-06T12:46:25Z

Exact metadata: [source record](sources/issue-5356286656-6bba629d7800c75ef433fdc6f1f5747ca99ad305229a0c31a8cf5cb46110f5a9.json).

**Status: Movement/noise research is done; the final seven conditions are not.** Only cover, lantern and weather comparisons remain.

Verify installation of the follow-up probe and resolve manual lantern control in #105 first. Then supply the short F9-gated test sequence. Do not ask you to repeat completed movement trials or infer a universal detection meter.

## comment 5550112385 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/113#issuecomment-5550112385

Created: 2026-08-06T03:58:32Z; updated: 2026-08-06T03:58:32Z

Exact metadata: [source record](sources/comment-5550112385-f86a5db2187cde631e0e2ab2d0147ceb329eceadf044d08a7f95f5b994073299.json).

Research result: the reusable audit already exists in `docs/STEALTH_SYSTEM_AUDIT.md` and the settled Stealth/perception sections of `CODEX.txt`. RDR2 layers perception data, noise, visibility/LOS, crouch movement, and a separate stealth-movement state; there is no supported universal detection-meter value or per-model stealth stat. `StealthProbe` can log the relevant state, but the earlier scripted-guard experiment was not a valid controlled observer. The next meaningful research is a self-verifying free-roam observer matrix across distance, angle, lighting, cover, stance, speed, noise, and weather. Preserve the existing data/editor exposure; do not invent a single “stealth multiplier” until that probe establishes one.

## comment 5550112401 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/113#issuecomment-5550112401

Created: 2026-08-06T14:07:51Z; updated: 2026-08-06T14:07:51Z

Exact metadata: [source record](sources/comment-5550112401-b84b9020b70aa4beeb0db23c3f0330f53c916e8a7ea33b0fb2cda834c4739b0f.json).

The earlier probe did not answer the requested gameplay question, and its hostile phase was invalid because the observer remained under an indefinite TASK_STAND_STILL. That null result is withdrawn. A replacement hostile-detection probe is now built and installed (SHA-256 D2BD5042D6BB2512442396B8C07BF1B0E8EF7E8C67875CB3D73B0677C360BEF5). It uses a fresh active hostile guard per trial and logs actual combat/flee/event transitions at 20 Hz across day/night sight distances, stance and locomotion, sound-only movement, 100-1000 ms visibility pulses, cover/LOS, lantern off/on, and clear/rain/fog. The audit remains incomplete and this issue remains actionable until the in-game matrix is run and analyzed. Lexer-Lux/Lexeditor#119 does not have sufficient evidence for acceptance before those results.

## comment 5550112415 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/113#issuecomment-5550112415

Created: 2026-08-09T07:26:28Z; updated: 2026-08-09T07:26:28Z

Exact metadata: [source record](sources/comment-5550112415-4fb2c9813a60defdf356584ffe2d785c90d1e5b9cb749e5b4c45ea0cb981f899.json).

Runtime evidence check on 2026-08-09: the three files created after the hostile-matrix build (081726, 084211, 084427) contain only probe_loaded. They have no F7/arming event, observer verification, trial samples, or completion event, so the hostile matrix was not executed and they contain no stealth result. StealthProbe.asi was also absent from the game root at the latest recorded launch. I rebuilt and reinstalled it with an explicit five-second idle heartbeat that distinguishes not_executed_waiting_for_F7, executed_probe_failed, and executed_probe_complete. Installed SHA-256: 512EC04AE6E82562E4A41BBDCD8BA1356458D503E481ECF23B614E662979E621. Issue remains needs a human until one complete matrix CSV exists; no audit conclusion or Lexer-Lux/Lexeditor#119 acceptance is claimed.

## comment 5550112431 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/113#issuecomment-5550112431

Created: 2026-08-10T06:20:17Z; updated: 2026-08-10T06:20:17Z

Exact metadata: [source record](sources/comment-5550112431-1cda8e01112e83a43978709d37635f72a0c08433bc7af5746700721ecddffa61.json).

The partial 20260809-232527 run was analyzed. I retained its measured movement/noise data and removed those trials from the follow-up. The replacement now waits for F9 before cover, lantern off/on, and clear-weather sampling. It built successfully. I did not overwrite the ASI loaded by the current RDR2 process.

## comment 5550112447 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/113#issuecomment-5550112447

Created: 2026-08-10T06:22:49Z; updated: 2026-08-10T06:27:21Z

Exact metadata: [source record](sources/comment-5550112447-6de50f80a8eddf43b1b733baee3345118b64ee12e41f758abbe1953154165462.json).

The rebuilt short follow-up ASI is queued for a standalone install after the current RDR2 process closes. Source SHA-256: 5269B4D62CDC2E8CE0DDF8B5B7CF86393E940D13BD41E282EFE319903E558A5E. F9 now rejects cover/lantern conditions when the recorded cover, LOS, distance, facing, or equipped-weapon state is wrong. The watcher copies only StealthProbe.asi and then verifies its installed hash; it does not touch the combined GameplayTweaks build.
