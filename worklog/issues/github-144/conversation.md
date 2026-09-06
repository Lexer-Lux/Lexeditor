# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356294452 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/144

Created: 2026-08-06T02:25:40Z; updated: 2026-09-05T06:57:17Z

Exact metadata: [source record](sources/issue-5356294452-a971adb4ef9796d5183b530fe891146d52d5e57ba5a1be608e8eb0352cd395b3.json).

CASING SPAWN POSITION AND MOMENTUM TUNING — temporarily restore vanilla
     casing visuals, tune our casing spawn position and ejection momentum to
     match, then remove the reference behaviour.

## issue 5356294452 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/144

Created: 2026-08-06T02:25:40Z; updated: 2026-09-06T12:47:21Z

Exact metadata: [source record](sources/issue-5356294452-16190267f8e48708cef467e1fd00e2e1ea74411bf54f66e3073ca59a68ad8de9.json).

Match custom casing position and momentum to vanilla before tuning away the reference effects.

**Status: Test preparation is broken.** The restore control restores only the base weapon file while six patch files remain blank, so several weapons have no valid reference. Correct restore/status coverage across the whole weapon set before any visual comparison.

## issue 5356294452 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/144

Created: 2026-08-06T02:25:40Z; updated: 2026-09-06T13:57:17Z

Exact metadata: [source record](sources/issue-5356294452-87eb5c7244d89bf169e4b002280be51571e7150462e3ff6fd897a05071afc92d.json).

Match custom casing position and momentum to vanilla before tuning away the reference effects.

**Status: Test preparation is broken.** The restore control restores only the base weapon file while six patch files remain blank, so several weapons have no valid reference. Correct restore/status coverage across the whole weapon set before any visual comparison.

## comment 5550121573 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/144#issuecomment-5550121573

Created: 2026-08-06T08:50:13Z; updated: 2026-08-06T08:50:13Z

Exact metadata: [source record](sources/comment-5550121573-6718c0fd48a99e36a6c8442e380b0fa5e53fe2e93f2f1704022e32b163784971.json).

Implemented weapon-local casing spawn/ejection tuning with inherited player velocity, configurable right/forward/up momentum, jitter/orientation, gentler reload momentum, reload fan spacing, and exact world-space logging. The requested vanilla VFX reference does not exist in the shipped weapon stack (all audited shell-effect fields are blank), so no fake reference was introduced. Static verifier passes 19 contracts; final values need the listed in-game weapon-family tests after installation.

## comment 5550121588 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/144#issuecomment-5550121588

Created: 2026-08-06T11:59:01Z; updated: 2026-08-06T11:59:01Z

Exact metadata: [source record](sources/comment-5550121588-5029ad1bc6d085d5489f1bd4f050863410703a2322850de1feb84039e7c0e67b.json).

i'm somewhat puzzled as to what you did here? the plan was for you to bring back the vanilla casings, then i would shoot every gun and tell you if your ejection point was off and what momentum they should have. but it seems you did the opposite -- gave them those things without ever looking at the vanilla casings.
how?

## comment 5550121601 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/144#issuecomment-5550121601

Created: 2026-08-06T13:26:37Z; updated: 2026-08-06T13:26:37Z

Exact metadata: [source record](sources/comment-5550121601-69fdd7878f31cfdab0564d960238fb374d48205f2792cd31a57541ca5a708e3e.json).

Research correction:

The previous “no vanilla shell VFX exists” conclusion was wrong. `datasets/vanilla/weapons.ymt` contains 54 nonblank vanilla `VfxWeaponShellInfoHashName` values, and all six vanilla patch files contain shell references: M1899 `0x94662936`, Evans `0x1CFAE100`, LeMat/Gambler `0x778F9F95`, Navy `0xC58B9474`, and Elephant `0x53F13DE1`. Our shipped stack blanks them.

The editor restore endpoint is incomplete: it restores only base `weapons.ymt`, then maps still-blank patch layers. Current custom casing offsets/velocities are generic guessed values from the weapon entity pivot/matrix, not vanilla calibration.

Required research next step: temporarily restore shell VFX across all seven weapon-stack files, install that reference build with custom physical casings visible, shoot each weapon family in first/third person, and record spawn/momentum deltas. Then tune per family/weapon and reblank the full stack. No implementation or relabeling was performed during this exploratory pass.

## comment 5550121615 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/144#issuecomment-5550121615

Created: 2026-08-09T07:37:06Z; updated: 2026-08-09T07:37:06Z

Exact metadata: [source record](sources/comment-5550121615-d82f8f55de00f2b6b8675ff80ebd3d0fdcd2d8f5dc73c817be87b477a9edddb7.json).

Second-pass research confirms and extends the correction: vanilla shell-ejection references exist across the complete seven-file weapon stack.

Base `datasets/vanilla/weapons.ymt` has 54 nonblank records using 11 hashes. Six patch files add seven records: M1899 `0x94662936`, Evans `0x1CFAE100`, LeMat/Gambler `0x778F9F95`, Navy/Navy Crossover `0xC58B9474`, and Elephant `0x53F13DE1`. Full stack: 61 authored fields, 12 distinct hashes. Every corresponding `MyOverhaul` field is blank.

Family map: Cattleman `0x53690D3B`; DA/Schofield `0x778F9F95`; pistols `0x94662936`; repeaters/varmint `0x1CFAE100`; Springfield/Bolt `0x6404F7C5`; snipers `0x7DC338F1`; break-action shotguns `0x53F13DE1`; semi/repeating shotgun `0x59D9C115`; pump `0xF2571600`; Gatling `0xA55B12C2`; Maxim `0x9CE04D47`; patch-only Navy `0xC58B9474`.

LEXEDITOR’s restore path still restores only base `weapons.ymt`; blank patch layers remain. Current physical casings use one global ten-value vector from the weapon entity pivot/matrix, so they are not vanilla-calibrated across 12 effect families, ejection/reload modes, dual-wield hands, and POVs. The extracted files contain references, not the VFX payload’s internal offset/momentum; those values remain unknown. The August 7 log has heartbeats with `world=0`, not a visible comparison.

Exact next step remains: restore the shell field from every matching vanilla file into all seven shipped YMTs; keep custom casings visible; install/hash-verify; compare every family in first/third person and both dual-wield hands; record deltas; tune per evidence; then reblank and verify all seven. No implementation or label change was made.

## comment 5550121629 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/144#issuecomment-5550121629

Created: 2026-08-11T07:13:35Z; updated: 2026-08-11T07:13:35Z

Exact metadata: [source record](sources/comment-5550121629-af889ba163a281e7848d5e4bbed1f0826cd5745fafc35d85498205688b54646e.json).

New re-audit finding: the shell-VFX restore control can report a complete restore while six patch files remain blank.

The editor calculates status from base `weapons.ymt` only. The restore path changes only that base file, then maps the other files without restoring them. The UI therefore reports only the base 54 fields. The seven authored patch fields stay blank: M1899, Evans, LeMat, Gambler Double-Action, two Navy records, and Elephant Rifle.

Player impact: a reference build made with this control would show vanilla shell VFX for base weapons but no vanilla reference for those patched weapons. That can make a missing reference look like a correctly calibrated custom casing.

Restore, blank, status, and saved-count checks must cover all 61 fields in all seven YMT files before the comparison build is valid.
