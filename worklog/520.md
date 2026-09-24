# #520 — Create GUI

## State (2026-09-23 per-game-ff7r pass)

- Source already present: shared-control screens in `games/ff7r/editor.js`
  (+ `tables.js`, `panels.js`, `views.js`, `inputs.js`), semantic help,
  game-key record identity (commit `dc469bf0`, covered by
  `tests/test_ff7r_record_identity.py`), honest Data Map navigation with
  single-source split modules (commit `dc3cdc28`). PR #488 (FF7R-1 Plugin)
  is merged.
- Tests: `tests/test_ff7r_record_identity.py`,
  `tests/test_ff7r_completion_contract.py` pass (full ff7r selection:
  519 passed). No code change needed on this branch.

## Needs Lexer (installed game + rendered UI)

- Inspect rendered interaction and screenshots at desktop, narrow windows, and
  large UI scale; fix defects before exact-head candidate delivery. No
  agent-side browser run in this pass claimed rendered proof.
