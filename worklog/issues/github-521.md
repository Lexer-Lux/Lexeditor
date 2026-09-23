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
