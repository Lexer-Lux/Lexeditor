# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5365461389 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/363

Created: 2026-09-06T14:10:36Z; updated: 2026-09-06T14:10:36Z

Exact metadata: [source record](sources/issue-5365461389-6996efb85ec6d47b3e453e876b0399bf77491c7c8abc121ba806e2634f87ccb9.json).

## Requested outcome
Allow **Shared Magic Inventory** and **Party Switch** to be enabled and used together in the same mod. The user explicitly requested this compatibility defect be fixed; disabling either feature is not the requested solution.

## Current delivery and limitation
PR #356 (merged as `991598efd0948fb0fe89b6781f0809c825161bba`) shipped the rebuilt native driver with the standalone Party Switch repair. Its delivery notes explicitly retain the block on combining Party Switch with Shared Magic Inventory pending separate compatibility validation. See `worklog/issues/github-356.md`.

The known limitation is the deliberate configuration/runtime compatibility restriction. The underlying combined-runtime failure mode has **not** been established by that delivery; investigate rather than assuming a particular memory bug. Do not merely delete the safety check and declare compatibility.

## Required work
- Trace shared-pool ownership, active/reserve character mappings, junction quantities, and native switch callbacks. Implement safe synchronization across the whole replacement transition, including cancellation and failure recovery.
- Preserve the existing Party Switch behavior: visible living-reserve names, replacement of only the acting character, a spent turn on success, cancellation preserving the turn, refreshed name/HP, and no soft-lock.
- Keep one authoritative spell pool across menus, Draw, casting, junctioning, switching, and save/reload. Prevent stock loss, duplication, stale per-character copies, and migration being rerun during a switch.
- Remove the mutual-exclusion restriction only once the supported combination passes regression checks. Preserve unrelated safety checks and per-mod setting persistence.
- Deliver the rebuilt Windows driver, complete source patch, manifest, independent artifact pins, and installation path together—not source-only changes.

## Acceptance criteria
- [ ] Both settings can be enabled, saved, reopened, and installed together at the currently supported stock cap of 100. Non-100 shared-stock compatibility remains separately tracked in #94.
- [ ] Switch each of the three active slots to a living reserve and back, repeatedly; names/HP refresh, ATB behaves correctly, and battle input returns.
- [ ] Cancel selection and exercise unavailable-reserve/failed-transition cases without losing the ready turn, corrupting party state, or modifying spell stocks.
- [ ] Draw and cast before and after switches; stock changes occur exactly once and all menus/junction quantities reflect the shared pool.
- [ ] Finish battle, save, reload, and verify party, stocks, and junctions. Exercise supported setting-disable/migration paths without loss or duplication.
- [ ] Existing standalone Party Switch and Shared Magic regressions still pass; package/Windows installer checks pass for the delivered bytes.
- [ ] Supply a reproducible copied-save/encounter test procedure and record expected versus observed results. Distinguish automated/emulated checks from actual in-game acceptance; never publish private game executables or save data.

Related: #310 (shared magic), #313 (Party Switch), #94 (stock caps), #356 (delivered standalone native repairs).
