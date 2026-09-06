# #60: Finish stat-curve appearance and live editing

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/60)

## Requirements and decisions

Character/GF stat graphs need live coefficient editing, sensible stat-specific ranges, no white prototype fill, and a title/formula arrangement that does not overlap. GF graphs use the same shared curve machinery rather than a separate legacy widget.

## Current implementation and evidence

FF8 now uses a translucent game-coloured curve fill. The shared curve editor lays heading, variables, plot, formula and status in separate grid rows; FF8 centers its graph heading and keeps it pointer-safe. Shared pointer hover evaluates the current edited curve. PR #379 added fail-closed contracts for these properties plus the GF shared-curve route, and exact-head Linux source/UI and Windows package/install jobs passed before merge.

The live issue is `untested`: code/CI coverage is complete, but visual acceptance has not been claimed.

## Next agent work

No implementation defect is currently known. Human acceptance should check title/formula separation, non-white fill, immediate redraw and hover after edits, HP's larger axis, GF parity and Save/reload. Reopen agent work only for a reproduced visual or persistence failure.
