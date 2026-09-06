# #32: Finish the GF layout and shared graphs

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/32)

## Requirements and decisions

GF detail must keep Compatibility left, General center and Abilities right, with the five GF HP/level coefficients using the same shared curve controls as the other stat graphs. Unsaved edits, all 16 GF records and save/readback must survive the layout work.

## Current implementation and evidence

The active renderer uses `panelLayout(..., "gf-three-panel", ...)`, marks Compatibility and Abilities explicitly, and routes all five GF curve fields through `gfStatGrowth` in General. PR #379 added fail-closed source contracts for this wiring and ran them with the existing FF8 regression suite. Its exact-head Linux source/UI and Windows package/install jobs passed before merge (`beb4553e080d2222bea7320de6f2b180f9f7812a`).

The live issue is `untested`, not complete: automated coverage proves the shipped structure, but not a player's visual acceptance.

## Next agent work

No implementation defect is currently known. Human acceptance should check the three-pane layout at normal/narrow widths, immediate graph redraw, unsaved GF switching, all 16 selectors and Save/reload readback. Reopen agent work only for a reproduced failure.
