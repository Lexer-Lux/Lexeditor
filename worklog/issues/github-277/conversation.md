# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356327520 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/277

Created: 2026-08-12T11:58:45Z; updated: 2026-09-05T07:04:22Z

Exact metadata: [source record](sources/issue-5356327520-9fcd364be97831e0e159fea210a1f37473bea25644f0199506bc229495fc0a53.json).

(No body was present in this captured version.)

## issue 5356327520 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/277

Created: 2026-08-12T11:58:45Z; updated: 2026-09-06T12:57:08Z

Exact metadata: [source record](sources/issue-5356327520-9e3fe12621d81f3ea3fd1a807c1d048e82f61d0a0645b43bb0e36302cfa30989.json).

Hide Recon displays and acquisition during actual story cutscenes, then restore existing tags afterward. Cinematic camera mode alone is not a cutscene detector.

**Status: A corrected cutscene-aware implementation is described, but its installed handoff is not confirmed.** Verify that candidate and prepare a real cutscene check before asking you to repeat the failed test.

## issue 5356327520 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/277

Created: 2026-08-12T11:58:45Z; updated: 2026-09-06T12:57:08Z

Exact metadata: [source record](sources/issue-5356327520-f03609575cc4bf285cfc70900963fb588fdba3b1a116a10b1330414e3ed588c2.json).

Hide Recon displays and acquisition during actual story cutscenes, then restore existing tags afterward. Cinematic camera mode alone is not a cutscene detector.

**Status: A corrected cutscene-aware implementation is described, but its installed handoff is not confirmed.** Verify that candidate and prepare a real cutscene check before asking you to repeat the failed test.

## comment 5550160697 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/277#issuecomment-5550160697

Created: 2026-08-12T13:07:39Z; updated: 2026-08-12T13:07:39Z

Exact metadata: [source record](sources/comment-5550160697-a45b1cad79219a871016d054ae14f985cc32aa0e7211fa3bdfce86a443f18b0d.json).

Recon world tags, plant tags, acquisition progress, prompts, and minimap mutations now stop while the cinematic camera renders; completed tags are preserved. Start a cutscene with completed tags in view: no recon display may appear during it, and the completed tags must return afterward.

## comment 5550160709 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/277#issuecomment-5550160709

Created: 2026-08-13T12:38:54Z; updated: 2026-08-13T12:38:54Z

Exact metadata: [source record](sources/comment-5550160709-c523cefb996685bd6b943f7fa007ab601595706bb8a00c072ec8e8a4bc736619.json).

No change.

## comment 5550160723 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/277#issuecomment-5550160723

Created: 2026-08-14T00:25:59Z; updated: 2026-08-14T00:25:59Z

Exact metadata: [source record](sources/comment-5550160723-72cd02d16ed1e9874a6ebb0e6266c274afb5d85642c4fc14e9ceea4c1df3c02f.json).

**"No change" was right, and the reason is that the old gate could not fire during a cutscene.**

The previous fix suppressed recon on `IS_CINEMATIC_CAM_RENDERING()`. That native reports the cinematic **camera mode** — the one you toggle — not a story cutscene. Your session proves it never triggered: across every recon heartbeat the gate reported only `notaiming`, `unavailable` and `weaponwheel`. The string `cinematic` never appears once.

RDR2 has no `IS_CUTSCENE_ACTIVE` native, which is why this was missed. Rockstar's actual overlay-visibility predicate is `camp_beaverhollow.c` func_251 (`:7237`), repeated in every `camp_*.c` script, and it refuses to draw when **any** of three things is true:

1. `HUD::IS_HUD_HIDDEN()` — `:7239`
2. `CAM::IS_CINEMATIC_CAM_RENDERING()` — `:7243` (the only one we had)
3. a started anim scene — `:7248`: `_DOES_ANIM_SCENE_EXIST(Global_43800) && _IS_ANIM_SCENE_STARTED(Global_43800, false)`

That third one is the real cutscene test. `Global_43800` is the canonical current-scene handle — 1322 `EXIST` and 888 `STARTED` call sites across 907 scripts use exactly that global, so this is not an inference.

All three are now implemented. Completed tags stay in memory and return afterwards, exactly as before; nothing is drawn, acquired, prompted, scanned or blip-mutated while any of the three holds.

The heartbeat now names which term suppressed it — `hud-hidden`, `cinematic` or `cutscene` — so if tags ever show through a cutscene again, the log says whether the gate failed to fire or fired and something else drew them. That distinction is what was missing.

Test: get a completed tag or two in view, then trigger a cutscene. No recon display during it, tags back afterwards.

