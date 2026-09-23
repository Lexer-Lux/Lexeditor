# #79: Complete FF7’s data editors

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/79)

## Current request / ownership

Lexer requested a fresh completion audit of the **classic FF7** plugin on `codex/ff7-plugin-completion`. This worker owns `plugins/ff7` and this issue handoff only. The separate FF7 2013 product adapter `plugins/ff7_2013/plugin.py` is out of scope.

Both product identities currently import/run shared `plugins.ff7` parser/server/editor code. No open FF7-2013 PR or branch was visible during the 2026-09-19 live inspection. Therefore shared `plugins/ff7` format changes in this PR must remain backward-compatible with both identities, and a separate FF7-2013 worker must coordinate before changing the same shared parser surface.

## Audit baseline

Live `master` at audit start: `a47f0a57f8b44113b0ca1d42e5795f59f707372a`.

Reviewed current guidance / references:
- `AGENTS.md` @ `ec8d363d7fa9b937c8849dfa4c13c7c0fc5d1fde`
- `docs/ADDING_A_GAME.md` @ `78a987c5f61d3f28fb6f4195d08717c98dcb2af8`
- `docs/UI-MANUAL.md` @ `14a3269992031d7e7893fcb127728a48b944e71f`
- `plugins/blank/editor.html` @ `cd3c79bab8a5b13b3167a26e8fe4e0617c940802`
- `plugins/rdr2/editor.html` @ `9d11f8a0bd35526dbb4959fd3e964a4f72472718`
- `codex/ff7-data.md` @ `00b63e396487461d8bc8ca82bfc1872a45800848`
- `ui/component-catalog.js` is not present on current master (GitHub 404); do not invent a substitute path.

Live issue #79 and its comments were reread. PR #434 is merged/closed, so it cannot be reused. Its 38-dataset parser/editor completion and preservation fixes are already on master; its synthetic/browser evidence is historical evidence, not current installed-game acceptance.

## Requirement / gap / evidence

- **38 format-specific editor categories:** implemented and navigable in the shared FF7 page. Data Map intentionally reports many as `partial` because only documented fields are writable; this is not permission to relabel opaque bytes or unrelated field/world data as complete.
- **Safe round-trip:** strict source/active snapshots, project-only binary writes, reparse/readback and no-op preservation exist. Current source families are KERNEL, scene, kernel2 text, recognized English executable, field encounters and world encounters.
- **Semantic UI:** current page uses shared controls and has record identities/references/help, but the page is still one large inline HTML/JS implementation. Audit modularization and the current Table+Detail contract before changing behavior.
- **Data Map truthfulness:** server currently maps readable structured rows to `coverage=structured` while retaining `status=partial`; unreadable rows remain unavailable. Audit every row against actual parser bounds and current public format knowledge rather than bulk-promoting status.
- **Deployment / loading:** not implemented for classic FF7. `ui/mod-loading.json` explicitly says project saves are not deployed. Current setup seeds only a project KERNEL baseline and interface sounds.
- **Runtime/helper integration:** FFNx configuration editing exists when `FFNx.toml` is present, but this is not a complete mod deployment path. Current public FFNx documentation/source must be checked before choosing direct/override/Hext behavior. Do not guess executable-patch deployment.
- **Helpers / Updates:** no new third-party helper is bundled by the classic FF7 plugin today. If a helper is introduced, it needs a pinned redistributable license-safe bundle, first-time setup, shared Updates entry and silent-updater disablement; otherwise record the limitation.
- **Acceptance:** current master has prior synthetic and Chromium evidence plus the installed-data checker. No new candidate, exact-head rendered screenshots, actual deployment, or real-game gameplay acceptance has yet been established for this completion branch.

## Public research to verify before code expansion

Existing durable references remain Elena, ff7tools, Scarlet and the FF7 format wikis in `codex/ff7-data.md`. Re-check current FFNx / 7th Heaven / Makou Reactor / Scarlet / ff7tk source and licensing before materially relying on them. Record any materially used source/license in FF7 Credits/third-party notices as implementation lands.

## Worker session 2026-09-23 (per-game-ff7 @ e0e15a63)

PR #434 is merged; per-game-ff7 contained no unique commits, so the branch was
fast-forwarded to origin/master e0e15a63. Issue #79 stays open: remaining scope
is installed-game acceptance (Lexer's `tools\FF7-checks.cmd` on both editions,
disposable-mod edit/save/reopen, native deployment/gameplay proof).

Found and fixed stale FF7 verifier scope after split d2711bbe (editor.js ->
editor.js/controls.js/details.js/workspace.js), matching the pattern already
used by verify_ff7_ui.py:159:
- tools/verify_ff7_semantic_surface.py: scan all four page modules.
- tools/verify_ff7_blank_ui.py: scan all four page modules.
- tools/verify_ff7_rendered.py, tools/verify_ff7_rendered_neutral.py,
  tools/verify_ff7_2013_rendered.py: inline all four page modules in page order
  (harness previously loaded editor.js only, so every rendered test timed out
  on `state.loaded`; this matches CI run 35915917245's TimeoutError set and its
  `return "";` binary failure).
- tools/verify_ff7_2013_rendered.py: follow shared Data Map simplification
  87f53379 ("Filter files by coverage"/"Structured editable" ->
  "Filter files by integration"/"Partial").

Evidence (Windows, worktree C:\Lexeditor\_worktrees\ff7): all 12 FF7 python
verifiers exit 0; all 7 ui_neutral browser scenarios pass; rendered_neutral
8/14 pass; exe_rendered 1/1; 2013_rendered 1/1. Residual: 6 narrow-viewport
subtests (dense-custom-views characters/encounters, master-headers
items/armor/materia/encounters) fail locally with 6-12px header/control
overflow at 900px width and zero overflow at 1200px; shared columnList sizing
is font-metric sensitive, so Ubuntu CI must adjudicate. CI never evaluated
these subtests (all 14 errored on load).

Next: watch FF7 CI on the pushed branch; installed-game acceptance remains
with Lexer (checklist in live issue #79). No game-code changes were made.

## Next agent work

1. Audit every Data Map row against the current parser field set and current public documentation/tooling; keep unsupported semantics explicit.
2. Audit current FF7 UI against shared paged Table+Detail, loading/empty/error, save/discard/reopen, responsive and Data Map/Info navigation requirements; fix plugin-local gaps without editing shared framework files.
3. Establish a documented, reversible project-to-game export/deployment path only where current FFNx/current-release behavior is authoritative; fail closed elsewhere.
4. Add/refresh synthetic round-trip and plugin-scoped rendered interaction evidence, inspect retained screenshots, then package an isolated candidate without touching an existing Lexeditor installation.
5. Update the draft PR with exact requirement/gap/evidence/remaining-real-game acceptance. Keep issue status actionable while agent-side work remains.

## Worker session 2026-09-23 (impl/misc-games @ 7bf81c04)

- Repaired `tools/verify_ff7_blank_ui.py`: its `BLANK*` paths still pointed at
  `games/blank/*`, removed by the plugins rename, so the verifier died with
  `FileNotFoundError` before any check. Ported to `plugins/blank/*`; the
  contract (zero local CSS, shared neutral presentation, current Blank
  geometry) passes unmodified.
- Evidence, same head: all 12 FF7 python verifiers exit 0
  (`verify_ff7_datasets`, `kernel_layout_contract`, `accessories`,
  `semantic_surface`, `extended`, `completion`, `deployment` 6 tests,
  `tooling` 6 tests, `mod_stack` 6 tests, `installed_contract` 3 tests,
  `edition_parity`, `blank_ui`). Rendered browser scenarios are left to CI.
- No game-code changes. Remaining scope is installed-game acceptance with Lexer
  (checklist in live issue #79). Issue stays `actionable`.
