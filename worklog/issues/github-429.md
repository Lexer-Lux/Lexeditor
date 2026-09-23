# #429 — Better Lock-on, red reticle instead of LOCK ON text

## State (2026-09-23 per-game-ff7r pass)

- Source already present: `games/ff7r/lockon_tweaks.py` with research probes
  `games/ff7r/lockon_probe.py`, `games/ff7r/lockon_text_probe.py`,
  `games/ff7r/lockon_slot_asset_probe.py` (suppress lock-on text, tint only
  the active reticle red; targeting/camera/switching untouched; localization
  preserved by suppressing the presentation element).
- Tests: `tests/test_ff7r_lockon_tweaks.py`, `tests/test_ff7r_lockon_probe.py`,
  `tests/test_ff7r_lockon_slot_asset_probe.py`,
  `tests/test_ff7r_lockon_text_probe.py` pass (full ff7r selection: 519
  passed). No code change needed on this branch.

## Needs Lexer (installed game)

- Unlocked: normal reticle, no UI changes. Locked: reticle red, `LOCK ON`
  text absent. Target switch/loss updates immediately. Disabled: vanilla UI.
