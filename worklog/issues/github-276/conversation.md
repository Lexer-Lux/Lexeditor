# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356327296 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/276

Created: 2026-08-12T11:57:29Z; updated: 2026-09-05T07:04:18Z

Exact metadata: [source record](sources/issue-5356327296-d18cd76ef40243ffdfa5b78d2aaa7610759ed64a777b4725fe2876e18c1d7745.json).

Remove arbitrary tonic gating. Set the amount of time it takes to grow a stage. How stored? Can change?

## issue 5356327296 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/276

Created: 2026-08-12T11:57:29Z; updated: 2026-09-06T12:57:07Z

Exact metadata: [source record](sources/issue-5356327296-58f45368aea2db222a3d005f3f2b6ebca65124499cf7c9837d9f52ac12d072bf.json).

**Status: Research complete; no implementation yet.** The tonic requirement for late stages can be removed while making stage duration configurable.

- [ ] Choose whether tonic remains an optional 2×/4×/8× accelerator, or the configured stage duration is exact and ignores tonic acceleration. Tonic will not be required for growth under either choice.

## issue 5356327296 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/276

Created: 2026-08-12T11:57:29Z; updated: 2026-09-06T12:57:07Z

Exact metadata: [source record](sources/issue-5356327296-d8a5f33ff3bb828c51150c221fe5e9b95defcd54376d71cd4532ddcc04cb536c.json).

**Status: Research complete; no implementation yet.** The tonic requirement for late stages can be removed while making stage duration configurable.

- [ ] Choose whether tonic remains an optional 2×/4×/8× accelerator, or the configured stage duration is exact and ignores tonic acceleration. Tonic will not be required for growth under either choice.

## comment 5550160383 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/276#issuecomment-5550160383

Created: 2026-08-12T12:06:58Z; updated: 2026-08-12T12:06:58Z

Exact metadata: [source record](sources/comment-5550160383-c137e2bd3f851840c1bf42c8c48687054a082204fd135ac3022d5d4c3ce83b60.json).

Research found the full Story Mode mechanism. Beard growth is stored in save-backed script state, not in `catalog_sp.ymt` or another editable item-data value.

`Global_40.f_7731[0..2]` contains chin, chops, and moustache. Each record stores the current stage, tonic acceleration tier, packed game-clock deadline for the next stage, and late-stage tonic allowance.

The base delay for stages 0 through 9 is hard-coded as 2, 2, 4, 8, 12, 20, 20, 32, 32, and 52 game hours. Hair Tonic applies 2x, 4x, or 8x acceleration. From stage 7 onward, the normal controller refuses to grow a beard part unless its tonic allowance is positive, then consumes one allowance after growth. That is the arbitrary gate.

The requested feature is feasible. `BeardGrowthHoursPerStage` can retime each part's saved deadline, while the mod keeps the late-stage allowance positive so stages 7 through 10 no longer require tonic. The saved deadline stays in `Global_40`; only the selected duration belongs in the INI. A hot change can preserve the fraction of the current stage already completed.

The controller must write only when the setting changes, a beard stage changes, or tonic changes the schedule. It must not force stages or rewrite save globals every frame. Readback must confirm stage, tonic tier, allowance, and deadline before and after each write.

One design choice remains: Hair Tonic can stay as an optional 2x/4x/8x accelerator, or the configured duration can be exact and ignore tonic acceleration. Tonic is no longer required as a gate in either design.

Acceptance must cover chin, chops, and moustache without tonic; exact game-hour timing; a duration change during a stage without lost progress; save/reload; sleep; camp and barber trims; and Arthur/John changes, with no rollback, instant jump, or repeated growth.

This is research only. No code, build, install, or issue state changed.
