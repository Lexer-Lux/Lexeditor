# #314: Finish custom commands and check the installed Draw/Shoot repairs

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/314)

## Requirements and decisions

- #93/GF Spellbook is no longer a code blocker; it has its own player-acceptance gate.
- Draw Once/Streamlined Draw and Irvine Shoot are implementation-complete, but gameplay acceptance is still required.
- Do not infer in-game success from source checks or CI.

## Current implementation and evidence

- `games/ff8/streamlined_draw.py` is integrated through `games/ff8/gameplay_settings.py` and owns Streamlined Draw filtering/selection behavior.
- `games/ff8/shoot_issue_54.py` owns the guarded Shoot queue, per-shot ATB cost, return/cancel handling, and next-ready lock.
- The live issue is now `untested` / `test build` with a reproducible player checklist. No gameplay acceptance has been claimed.

## Next agent work

Wait for the #314 player checklist result. If any step fails, move the issue back to `actionable` and start from the first failing Draw or Shoot path.
