# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356162771 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/97

Created: 2026-09-05T06:30:26Z; updated: 2026-09-05T06:32:37Z

Exact metadata: [source record](sources/issue-5356162771-56bdaa47b945f2b2b28ee2fe33995643fa9ea18235d3a8004fd888ae14835ad3.json).

Pressing Play in the Warband editor changes the button to Stop, but no playable game appears.

The shared host currently reports running immediately after starting the configured executable. That does not prove a game window or working game session. Check the selected executable, required Warband/WSE2 launch arguments, child-process handoff, and failure reporting.

Acceptance: Play starts the selected mod in a usable game window; a failed launch restores Play and shows the error; Stop tracks and closes the actual game.

Recorded for later investigation to respect the current work/budget limit. No game was launched for this report.

## issue 5356162771 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/97

Created: 2026-09-05T06:30:26Z; updated: 2026-09-06T13:02:21Z

Exact metadata: [source record](sources/issue-5356162771-f19c06c1adb002146e9dcd14da0b531ca520c104fb60e8d5ac6e4a3b9c13dc55.json).

PR #361 adds selected-module WSE2 launching, owned child-process tracking, a visible-window check, failure cleanup and Stop. Windows regression tests pass; no real game session has been tested.

**Still needs development:** stock/native `mb_warband.exe` launching is not implemented. Without WSE2, this branch reports an explicit error rather than pretending Play succeeded. This is not fully fixed and is not blocked on another design answer from you.
