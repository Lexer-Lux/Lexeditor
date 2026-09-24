# #432 — Editable item max carry capacity

## State (2026-09-23 per-game-ff7r pass)

- Source already present: `games/ff7r/semantics.py` economy surface exposes
  `MaxCount` beside the other per-item properties (buy/sell/can-sell),
  schema-validated against the installed Item/Equipment/Materia tables,
  project-overlay writes only.
- Tests: `tests/test_ff7r_semantics.py` and `tests/test_ff7r_editor_semantics.py`
  pass (full ff7r selection: 519 passed). No code change needed on this branch.

## Needs Lexer (installed game)

- Edit several different items and confirm actual in-game maximum held
  quantity changes; shop purchases and world/reward pickups respect the edited
  cap; capped items cannot exceed it through ordinary flows; unedited items
  keep vanilla capacity.
