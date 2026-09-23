# #307: Add a Bannerlord editor plugin

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/307)

## Requirements and decisions

Keep the implementation in draft PR #453 on `feature/bannerlord-plugin`. Do not merge, enable auto-merge, or treat source/API/CI checks as in-game acceptance. Durable Bannerlord integration rules are in `codex/bannerlord/project-memory.md`.

## Current implementation and evidence

- PR #453 is open/draft and implements the Bannerlord plugin, structured editors, Data Map, native module build/deploy/Play path, and conservative preservation/concurrency safeguards.
- Dedicated Bannerlord Linux, Windows, and Chromium checks passed at `44082678`.
- Final source-write hardening landed before that head and covers exact-byte revisions, stale-write rejection, BOM/newline preservation, and transactional helper writes.
- 2026-09-19 regression triage found two shared harness gaps exposed by Bannerlord:
  - `41d4c0c`: Data Map browser fixture now inlines safe plugin-local scripts instead of only one FF8 script.
  - `afcb5573`: shared screenshot/verifier fixture now creates an isolated valid Bannerlord module and fake install instead of falling back to `C:\\Bannermod`.
  - `01bba57e`: Bannerlord CI now includes the Bannerlord-scoped shared Data Map browser check and syntax coverage for the shared screenshot helper.
- GitHub did not schedule an Actions run for those connector-written commits during this session. Do not record the new harness changes as CI-passed until a run actually executes.
- Other observed failing workflows at the old head were unrelated infrastructure/other-game failures except for the two Bannerlord harness gaps above.
- 2026-09-23 exact-head verification at `5de3c63c` (master = origin/master): 208 Bannerlord pytest tests pass; rendered `bannerlord_browser_check` passes; `bannerlord_ui_audit_check` reports 57 checks with zero errors; Bannerlord-scoped shared Data Map browser check passes at all sizes; `test_data_map_coverage` passes. No `games/bannerlord` changes since the audited `7c6bb691`, so that rendered evidence remains current. Covers issues #513, #514, #515, #516 agent-side checks.
- Sources are recorded in shared `ui/credits.json` under `plugins.bannerlord` (source project plus BUTR BLSE/ModuleManager/XmlSchemas references). The Bannerlord theme is token-driven (`editor_boot.js`: accent `#8d2f25`, highlight `#a56b34`); no redistributed proprietary assets.

## Next work / acceptance

The plugin candidate still needs real installed-game acceptance. Do not invent additional plugin features solely to avoid that boundary.

Prepared check:
1. Select the real Bannerlord install and intended project.
2. Confirm Module, Data Map, Build, Deployment, and Runtime pages load normally.
3. Run Build + Deploy and verify module-owned output/backups plus exclusion of Runtime Override JSON from ordinary asset sync.
4. Use Play and confirm the resolved module loadout reaches Bannerlord without startup/module-loading errors.
5. Verify one reversible editor change through the running game, then revert it.
6. Capture the exact failing step and relevant Lexeditor/Bannerlord log text if acceptance fails.

Keep issue workflow status `actionable` until a usable current-head candidate/check is actually delivered and agent-side checks for that head are complete; then move to `untested` only when the remaining task is the prepared human acceptance test.

## 2026-09-23 per-game-bannerlord verification (issues #513, #514, #515, #516, #307)

No code changes were needed: every agent-verifiable check passes at the current head (see evidence above), and the remaining items in each issue require Lexer's installed game. Do not auto-close these issues on agent verification alone.

Exact Lexer needs per issue:
- #513 (Editor): per-area safe-editing completeness confirmation plus installed-game proof (steps 1-6 above).
- #514 (Mod Loading): real public mods in isolation (dependency conflicts, overlapping edits, Build + Deploy, Play loadout, backups, restoration), keeping installed-game results separate from synthetic tests.
- #515 (Theme): inspect the theme in the running game once a candidate is ready.
- #516 (GUI): confirm desktop, 900x620, and 150 percent-scale rendering against exact-head screenshots on the real setup.
- #307 (Plugin): full real-install acceptance checklist above, including one reversible Runtime Override change verified in the running game and then reverted.
