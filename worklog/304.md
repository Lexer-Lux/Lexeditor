# #304: Prepare the Vibration Consolidation test build

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/304)

## Requirements and decisions

Vibration Consolidation skips FFNx's extra one-item Vibration pause screen while preserving ordinary pause/resume behavior and the Config menu's Vibration setting. Keep field and battle paths separate in acceptance testing.

## Current implementation and evidence

The tweak is integrated into FF8 gameplay-settings Hext generation and activation. On 2026-09-06 the supported Steam-English `FF8_EN.exe` guard and Vibration static contract passed privately, and the full gameplay-settings persistence/composition verifier passed through the real Save/activation path. No executable or game asset was published.

The live issue was moved from `actionable` to `untested`: an implemented candidate and a concrete player checklist now exist, but no in-game acceptance is claimed.

## Next agent work

No implementation work is currently known. Preserve the issue's field pause, battle pause, stuck-rumble and Config checks; close only after those are observed in game or after a newly reported failure is repaired.
