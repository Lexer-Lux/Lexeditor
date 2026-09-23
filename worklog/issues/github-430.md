# #430 — Better Sprint, configurable sprint speed multiplier

## State (2026-09-23 per-game-ff7r pass)

- Source already present: `games/ff7r/sprint_probe.py` plus authority probe
  `games/ff7r/sprint_authority_probe.py`; `betterSprint` runtime config
  contract (`speedMultiplier`, `1.0x` = vanilla) with manifest hook gating;
  Runtime Tweaks editor surfacing (`BetterSprintEnabled`,
  `SprintSpeedMultiplier`, `BetterSprintHookValidated`).
- Tests: `tests/test_ff7r_better_sprint_runtime.py`,
  `tests/test_ff7r_sprint_authority_probe.py` pass (full ff7r selection:
  519 passed). No code change needed on this branch.

## Needs Lexer (installed game)

- Validate the sprint/run-speed hook against the installed build and record it
  in the runtime manifest (fail-closed). Then verify: `1.0x` matches vanilla,
  other values scale proportionally, walking/jogging and scripted/cutscene
  movement unaffected, disabled = vanilla.
