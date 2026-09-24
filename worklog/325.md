# #325: Prepare the Better Card battle fixtures

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/325)

## Requirements and decisions

Better Card excludes enemies whose two native Card-result bytes are both `FF`, disables Card when no valid enemy remains, and must coexist with Draw Once through the shared battle-command dispatcher.

## Current implementation and evidence

The supported Steam-English executable predicate/hook contract passed privately on 2026-09-06. The audit found a stale verifier assertion, not a runtime-layout defect: the composed Draw/Card scratch state is correctly 8 bytes (4-byte drawn mask plus 4-byte captured target). PR #377 corrected the verifier and merged as `3b72fed473aa590bd31b273fc9833e13b0d6902f`.

The corrected Better Card/shared-dispatcher verifier passes, and full gameplay-settings composition reports no overlapping reservations. The live issue is now `untested` with a reproducible Fire Cavern `Bomb ×2, Red Bat ×2` mixed-validity fixture and an all-invalid control.

## Next agent work

No implementation work is currently known. Human acceptance must confirm target filtering, command disabling when no valid target remains, and coexistence with Draw Once. Restore temporary enemy-card edits after the fixture test.
