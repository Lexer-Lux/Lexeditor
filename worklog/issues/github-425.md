# #425 — ATB Tweaks, configurable ATB generation and action costs

## State (2026-09-23 per-game-ff7r pass)

- Source already present: `games/ff7r/atb_tweaks.py` (data-backed controls)
  plus research probes `games/ff7r/atb_runtime_probe.py`,
  `games/ff7r/atb_authority_probe.py`, `games/ff7r/atb_attack_reference.py`,
  `games/ff7r/atb_speed_reference.py`, `games/ff7r/atb_movement_probe.py`,
  `games/ff7r/atb_dodge_transition_probe.py`,
  `games/ff7r/atb_resident_fingerprint.py` (passive/Speed/guard/hit-source
  semantics, movement multiplier, roll/dodge spend; accumulator paths
  unresolved until installed-build validation).
- Tests: `tests/test_ff7r_atb_tweaks.py` and all ATB probe tests pass (full
  ff7r selection: 519 passed). No code change needed on this branch.

## Needs Lexer (installed game)

- Validate the ATB accumulator/update paths against the installed build
  (per-hit vs per-attack vs damage-scaled hit gains, Speed/guard terms);
  verify each exposed coefficient composes with character/weapon/status
  modifiers and that movement/roll mechanics are inert when the tweak is off.
