# Worklog: Todo 175

## #175 — the replacement harness already existed, 2026-08-04

The TODO entry (and my own summaries) said the harness was dead and had to be
rebuilt before Lexer could be asked to play. That text described the OLD F10
controlled-observer experiment. `StealthProbe/script.cpp` was rewritten on
2026-07-28 AFTER that failure and already satisfies every requirement the entry
listed. Read the file before repeating the claim.

What it already does:
- Owns the whole experiment: spawns and dresses its own observer, drives a fixed
  scenario list on its own clock, writes every sample and transition to CSV.
- `verifyObserver()` is a hard gate in STAGE_ARMING - nothing runs until it
  passes. It checks: entity exists; model matches and is human and alive;
  grounded (`|z - GROUND_Z| < 1.5`); distance 8-25 m; `ENTITY_VISIBLE` flag; and
  `TRACKED_VISIBLE` with `TRACKED_PIXELS > 0`, i.e. genuinely rendering on
  Lexer's screen. Non-recoverable checks fail out after 8 s, the render check
  after 30 s, each with a stated reason.
- F7 arm/start, F8 abort and clean up, F9 manual marker and flush.
- Phases A and C move only the observer; only phase B needs the player and it
  auto-advances.

So the remaining work on #175 is not construction, it is ONE SESSION: stand on
open flat ground, no mission, no wanted level, press F7.

Fixed this build: the HUD line spacing (0.035 -> 0.048) that made the probe's own
text unreadable in Lexer's screenshot.

