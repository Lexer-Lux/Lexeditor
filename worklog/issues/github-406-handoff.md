# #406 — Plugin (FINAL FANTASY VII REMAKE INTERGRADE on PC)

## State (2026-09-23 per-game-ff7r pass)

- Source already present and reviewed: `games/ff7r/plugin.py` (Steam/Epic
  detection without a developer-local copy), `games/ff7r/pak_reader.py`
  (reads DataObject `.uasset`/`.uexp` from installed `.pak` archives),
  DataObject/text pipelines with unknown-byte preservation and project-only
  writes, mod `.pak` build plus explicit deploy to `End/Content/Paks/~mods`,
  parser/write round-trip and service smoke coverage. See the full
  implementation survey in `worklog/issues/github-406.md`.
- This branch adds: `minimapZoom` + `fieldCast` runtime config contracts and
  Runtime Tweaks surfacing (commit `cba2f0fa`; shared with #475/#474).
- Tests: full ff7r selection passes (519 passed), including
  `tests/test_ff7r_completion_contract.py` and
  `tests/test_ff7r_server_semantic_build.py`.

## Needs Lexer (installed game)

- End-to-end installed-game acceptance: detect the installed game, open
  DataObject/Text data from the real `.pak` archives, edit a price/carry/drop
  value, build and deploy the mod `.pak`, and confirm the game loads it with
  source archives untouched.
