# GitHub #481 — Better HP Colors

State: actionable until live acceptance. PR #500 is integrated with local work and PRs #499/#501/#502.

## Requirement / gap / evidence

- [x] True smooth RGB through FFNx vertex colour; no stepped approximation.
- [x] White 100%, yellow 50%, orange 25%, red 0%, piecewise linear.
- [x] Battle uses verified row/HP-glyph hooks.
- [x] Seven verified shared-character-widget menu callers use displayed computed current/max HP.
- [x] KO/full HP delegate; native non-white/yellow or pre-coloured presentation wins.
- [x] Unsupported native layout fails closed.
- [x] Default-off setting/UI/config and disabled driver dispatch to original `common_draw_paletted2D`.
- [x] Reconciled current master's newer gauge harness without changing production gauge behavior.
- [x] Active/reserve main-menu current-HP calls identified in the supported executable and hooked. Native status palettes still take priority; label, slash and maximum are unchanged. Reserve coordinate and character lookup cases added to the compiled harness.
- [x] Windows derivative build 35798579648 passed at f12a03d5; downloaded DLL SHA-256 `cf8aa19d233aa6cc69965ac8961759f5aadb7a1670926547e2ca07d052ad9621`. Its compilation inputs were compared with current source before packaging. Managed package pins, clean Git checkout and simulated upgrade checks passed.
- [ ] Live battle/shared-menu visual and disable comparison.

The interrupted stale head failed because its harness asserted pre-refactor gauge geometry and its generated `ff8_opengl.cpp` read `enable_ff8_better_hp_colors` without a declaration. This reconciliation preserves current master's gauge source and makes the driver call exported `lexeditor_ff8_hp_colors_requested()`, avoiding a cfg-global dependency. An unrelated FF7R shared-UI failure is outside #481.

A successful candidate packages `AF3DN.P`, `FFNx.toml.sample`, license/provenance, and `ISSUE481-ACCEPTANCE.txt`. Use only an isolated copy of the supported Steam English game. CI is not in-game acceptance.

Native/UI workflow 35799144379 passed on Windows and Linux. New settings pass browser toggle/help checks and independent config combinations. The managed runtime package contains the reviewed DLL; this task did not install it into the user's game.
