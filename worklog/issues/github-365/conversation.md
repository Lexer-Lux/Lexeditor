# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5366125119 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/365

Created: 2026-09-06T16:10:09Z; updated: 2026-09-06T16:10:09Z

Exact metadata: [source record](sources/issue-5366125119-e7af207cbb6d083aa1a27efb3b07f747944cedd8bf2e461a3c64c73939c6476e.json).

Bundle a fixed Lexeditor WSE2 package without the upstream updater; install/repair it explicitly and refuse unverified binaries at Play. Show pinned, installed and latest upstream versions in Home’s read-only helper checker (#81), with dates and release notes.

Steam achievements and features must remain supported. Package-level checks must not be presented as proof of a real Steam session. Implementation and acceptance preparation are in progress; the complete user request is preserved in `worklog/requests/wse2-managed-20260906/source.md` on `fix/warband-managed-wse2`.

## issue 5366125119 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/365

Created: 2026-09-06T16:10:09Z; updated: 2026-09-06T16:44:47Z

Exact metadata: [source record](sources/issue-5366125119-21be26d18936179a22b913acdde4cd20f5008c11bac440026653161b51febc3e.json).

Implemented and merged in #366 (`a494643` on master): bundled WSE2 v1.1.5.1 / package 1.1.5.1-lex1 without its updater, explicit backed-up Install/Repair, launch integrity checks, and Home’s read-only pinned/installed/latest versions, dates and release notes. Windows/Linux, rendered UI and diagnostic checks pass before and after merge. Publisher Steam components are preserved; actual Steam/game acceptance remains unverified.

- [ ] Update master, restart Lexeditor and close Warband/WSE2 launchers. On Home choose Warband → Install / Repair WSE2; no separate WSE2 download or build is needed.
- [ ] Open I AM LEXER → Helper Versions. Confirm pin/package and verified installed v1.1.5.1, publication date and release notes. Check again must only refresh information. Run `tools/Warband-checks.cmd`.
- [ ] Follow `docs/warband-managed-wse2.md`: verify the selected mod/load-save, overlay, playtime and used Steam features, then a normally earned eligible achievement. Report the exact failure, module/version and current game log; do not reset or force-unlock achievements.

## issue 5366125119 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/365

Created: 2026-09-06T16:10:09Z; updated: 2026-09-06T16:44:47Z

Exact metadata: [source record](sources/issue-5366125119-8738f042baac3d62cfe073ce28bb5c5c453a3834bb0239ec3f7063d3795b58af.json).

Bundle a fixed Lexeditor WSE2 package without the upstream updater; install/repair it explicitly and refuse unverified binaries at Play. Show pinned, installed and latest upstream versions in Home’s read-only helper checker (#81), with dates and release notes.

Steam achievements and features must remain supported. Package-level checks must not be presented as proof of a real Steam session. Implementation and acceptance preparation are in progress; the complete user request is preserved in `worklog/requests/wse2-managed-20260906/source.md` on `fix/warband-managed-wse2`.
