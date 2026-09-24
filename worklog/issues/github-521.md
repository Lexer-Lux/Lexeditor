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

## 2026-09-23 --- impl/misc-games: rename repairs verified, tracker unchanged

- The #525/#74 repair (`tests/test_ff9_datamap_gui.py` games-to-plugins port)
  is verified green; see `github-74.md`. No scope change for #522 (`waiting`,
  Lexer per-family decisions) or #523/#524/#525 (`untested`, human checklists
  stand). FFX-X2-adjacent files are untouched by this branch.
- Parent stays `actionable`; merging the misc-games PR must not close it.

## 2026-09-23 --- agents/actionables-ff9: audit, tracker unchanged

- Exact-head audit at origin/master 89f7f532 (branch agents/actionables-ff9): FF9 pytest 158 passed, node 18 passed, ff9 smoke/check/credits/features-determinism/rendered browser all pass; see github-74.md for the full list.
- No code change: #522 still waits on Lexer per-family pursue-or-exclude decisions, and #523/#524/#525 remain pending their human checklists. Parent stays actionable and must not be merge-closed.

## 2026-09-23 --- agents/actionables-ff9: implementation, tracker unchanged

- Implemented enemy-attack + battle-flag structured editing on this branch (see github-74.md); Data Map editable/placeholder distinction extended and contract-tested. `ui/credits.json` regenerated (it embeds the updated THIRD_PARTY.md citations).
- No scope change for #522 (still waiting on Lexer per-family decisions for battle geometry/assets and other p0data gaps) or #523/#524/#525 (human checklists stand). Parent stays actionable and must not be merge-closed.

## 2026-09-24 --- agents/actionables-ff9 merged (PR #563), parent flipped to waiting

- Last per-game branch merged after own-area verification (see github-74.md).
- Subissues: #522 `waiting`, #523/#524/#525 `untested`. Posted the parent
  checklist (all four subissue verifications, then the parent can close) and
  swapped `actionable` for `waiting`. 0 actionable / 0 open PRs repo-wide.
