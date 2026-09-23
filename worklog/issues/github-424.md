# #424 — Mark unscanned enemy names with ? in battle UI

## State (2026-09-23 per-game-ff7r pass)

- Source already present: `games/ff7r/unscanned_name_probe.py` plus
  `games/ff7r/unscanned_names_probe.py` (assessed/scanned runtime flag
  research; battle-name and ATB target-list render paths; runtime presentation
  change only, localization preserved, no internal IDs exposed).
- Tests: `tests/test_ff7r_unscanned_name_probe.py`,
  `tests/test_ff7r_unscanned_names_probe.py` pass (full ff7r selection:
  519 passed). No code change needed on this branch.

## Needs Lexer (installed game)

- Confirm the authoritative assessed/scanned flag and both render hooks
  against the installed build. Verify: unscanned shows `Enemy Name?` in
  battle UI and ATB target selection, suffix clears on scan/assess,
  already-scanned and boss/special targets unchanged.
