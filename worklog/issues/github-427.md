# #427 — HP Rebalance

## State (2026-09-23 per-game-ff7r pass)

- Source already present: `hpRebalance` runtime config contract
  (`hpMultiplier`, default `0.5x`, `1.0x` = vanilla) with manifest hook
  gating; research probes `games/ff7r/hp_rebalance_probe.py`,
  `games/ff7r/hp_recalc_sequence_probe.py`, bench probes
  (`bench_probe.py`, `bench_layout_probe.py`, `bench_coordinate_probe.py`,
  `bench_mutation_probe.py`) for the Chapter 3 bench-next-to-vending-machine
  removal (vending machine intact, no other rest points touched).
- Tests: `tests/test_ff7r_hp_rebalance_runtime.py`,
  `tests/test_ff7r_hp_rebalance_probe.py`,
  `tests/test_ff7r_hp_recalc_sequence_probe.py`, bench probe tests pass (full
  ff7r selection: 519 passed). No code change needed on this branch.

## Needs Lexer (installed game)

- Validate the max-HP hook against the installed build and record it in the
  manifest (fail-closed). Then verify: default `0.5x` halves every playable
  party member's max HP (integer rounding only), per-character progression/
  equipment differences preserved, current HP clamped to the new max, enemy HP
  untouched, bench removed only at the Chapter 3 site, disabled = vanilla.
