# GitHub #481 — Better HP Colors

State: actionable. Draft PR #500; FF8 only.

## Requirement / gap / evidence

- [x] True smooth RGB through FFNx vertex colour; no stepped approximation.
- [x] White 100%, yellow 50%, orange 25%, red 0%, piecewise linear.
- [x] Battle uses verified row/HP-glyph hooks.
- [x] Seven verified shared-character-widget menu callers use displayed computed current/max HP.
- [x] KO/full HP delegate; native non-white/yellow or pre-coloured presentation wins.
- [x] Unsupported native layout fails closed.
- [x] Default-off setting/UI/config and disabled driver dispatch to original `common_draw_paletted2D`.
- [x] Reconciled current master's newer gauge harness without changing production gauge behavior.
- [ ] Active/reserve main-menu HP-number seam is separate and has not been safely identified; do not guess it. Establish whether vanilla threshold-recolours it and, if so, its exact call seam.
- [ ] Current-head Windows derivative build + isolated candidate evidence.
- [ ] Live battle/shared-menu visual and disable comparison.

The interrupted stale head failed because its harness asserted pre-refactor gauge geometry and its generated `ff8_opengl.cpp` read `enable_ff8_better_hp_colors` without a declaration. This reconciliation preserves current master's gauge source and makes the driver call exported `lexeditor_ff8_hp_colors_requested()`, avoiding a cfg-global dependency. An unrelated FF7R shared-UI failure is outside #481.

A successful candidate packages `AF3DN.P`, `FFNx.toml.sample`, license/provenance, and `ISSUE481-ACCEPTANCE.txt`. Use only an isolated copy of the supported Steam English game. CI is not in-game acceptance.
