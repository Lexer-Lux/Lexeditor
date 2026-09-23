# #521 — FF9 plugin tracker

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/521)

## 2026-09-23 — per-game-ff9: branch status

`per-game-ff9` (from updated master `5de3c63c`) carries, one commit per issue:

- #524 — theme locked (shell `plugin.theme` + provenance note + node test).
- #525 — Data Map GUI contract locked (new `tests/test_ff9_datamap_gui.py`).
- #523 — no code change; agent-side mod loading complete, installed-game proof
  still required (exact checklist in `worklog/issues/github-523.md`).
- #522 — no code change; coverage gaps explicit, per-family Lexer decision
  still required (exact needs in `worklog/issues/github-522.md`).
- #74 — worklog status entry only; p0data codecs and in-game battle proof still
  required (exact needs in `worklog/issues/github-74.md`).

Only #524 and #525 are agent-complete; #522, #523, #74 stay actionable and must
not be merge-closed by this branch. Do not infer merge permission from issue
completion.

## 2026-09-23 --- per-game-ff9: verification session (no scope change)

- Branch now tracks master `e0e15a63`; this session adds one repair per issue:
  #523 helper-descriptor correction (`games/ff9/plugin.py`,
  `tests/test_ff9_runtime.py`), #524 credits-bundle regeneration
  (`ui/credits.json`), status notes in `github-523.md` and `github-74.md`.
- Full agent-side verification green (see `github-74.md` for the exact list).
- #522, #523, #74 stay actionable: per-family Lexer decisions and
  installed-game proof remain human work. Do not infer merge permission.
