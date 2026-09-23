# #413 — Configurable cutscene speed multiplier

## State (2026-09-23 per-game-ff7r pass)

- Source already present: `cutsceneSpeed` runtime config contract
  (`baseMultiplier > 1.0` enforced, `r2Behavior: multiply-native` so R2
  fast-forward compounds instead of replacing) with manifest hook gating;
  research probe `games/ff7r/cutscene_runtime_probe.py`; Runtime Tweaks editor
  surfacing (`CutsceneEnabled`, `CutsceneBaseMultiplier`, `CutsceneR2Behavior`).
- Tests: `tests/test_ff7r_runtime_config.py`,
  `tests/test_ff7r_cutscene_runtime_probe.py` pass (full ff7r selection:
  519 passed). No code change needed on this branch.

## Needs Lexer (installed game)

- Validate the cutscene hook/timing against the installed build and record it
  in the manifest (fail-closed). Then verify ordinary cutscene playback uses
  the configured multiplier and R2-held playback uses the compounded speed,
  with gameplay speed outside cutscenes untouched.
