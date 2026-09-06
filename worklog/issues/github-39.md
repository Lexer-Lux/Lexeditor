# #39: Finish the Enemy editor layout and runtime checks

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/39)

## Requirements and decisions

Enemy Stats, AI and Battle Text belong in the dedicated leading pane; Stats uses the shared stat-growth graph rather than the obsolete black prototype panel. Enemy AI/text writes need a real-game acceptance path. Broader format coverage remains #84.

## Current implementation and evidence

The active renderer attaches `enemyLeadingPanel` through the shared paged layout and switches Stats / AI / Battle Text inside `enemy-tabbed-column`; Stats calls `enemyStatGrowth`. Existing Chromium coverage exercises production Enemy controls, live edits, provenance and real `saveAll()` payload generation. PR #379 added a fail-closed contract for the pane/curve wiring and passed exact-head Linux and Windows checks before merge.

The live issue is `untested`. Runtime acceptance remains deliberately human-only.

## Next agent work

Use the live issue's reversible fixture: choose an enemy whose existing AI shows local battle text, mark two local lines, redirect the existing Show Text operand from line A to line B, Apply Source/Save/reload, trigger that same AI path in battle and confirm line B appears, then restore the original data. Reopen agent work only for a reproduced layout, compiler/readback or runtime failure.
