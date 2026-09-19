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
