# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356311961 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/219

Created: 2026-08-06T18:10:34Z; updated: 2026-09-05T07:01:11Z

Exact metadata: [source record](sources/issue-5356311961-ae1550b8fd350cbdaf90f3c3090a5e7c3cfdcc7c998a724262b3c3de41f76bf6.json).

GameplayTweaks currently writes dozens of separate subsystem log files, which makes a single crash or gameplay sequence unnecessarily difficult to reconstruct.

Replace the routine per-subsystem logs with one structured `GameplayTweaks.log` containing:

- one session-start record per game launch;
- timestamp/tick, subsystem, severity, and event fields on every entry;
- all existing useful diagnostic details without requiring cross-file timestamp matching;
- bounded size or rotation so it cannot grow indefinitely;
- normal versus development verbosity, with high-frequency traces disabled by default.

Acceptance: after exercising several GameplayTweaks systems in one session, their events appear in chronological order in the single log, routine subsystem-specific log files are no longer created, and a crash can be traced from that one file.

## issue 5356311961 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/219

Created: 2026-08-06T18:10:34Z; updated: 2026-09-06T13:17:48Z

Exact metadata: [source record](sources/issue-5356311961-dec05bb5f223b56da80d6e7a107e5d6925501467364edfd749a745e176df792b.json).

**Status: Closed after installation.** GameplayTweaks.log combines timestamped subsystem events, resets per session and rotates at a bounded size. Verbose tracing is off by default. Dedicated one-shot developer data exports remain separate; routine troubleshooting should not require dozens of logs.

## comment 5550141080 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/219#issuecomment-5550141080

Created: 2026-08-06T18:56:53Z; updated: 2026-08-06T18:56:53Z

Exact metadata: [source record](sources/comment-5550141080-5b39aa6934a777a17309a354a7699d6aed4c6ca4cadd85e7057cb9b471fd2678.json).

And don't forget to put some kind of limit somehow so the log file doesn't grow larger infinitely (which some of your current logs are doing)

## comment 5550141095 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/219#issuecomment-5550141095

Created: 2026-08-07T21:52:29Z; updated: 2026-08-07T21:52:29Z

Exact metadata: [source record](sources/comment-5550141095-eee2a3ff9623ae00d7b61a918e0e79ed467b596438bebd6215519571770ead0b.json).

Implemented and installed, SHA-256 `EF41BE120BA0D7ACCA6B9BF028073B699D53AD78B70DDA58D9429C6A38B97491`.

One file, `GameplayTweaks.log`, replacing ~47 per-subsystem files. Line format:

    <tick> +<ms since session start> <LEVEL> [subsystem] <event>

- One `session start` record per launch (build label, verbose flag, build date), then truncation, so a silent log is positive evidence a subsystem is not running.
- One monotonic clock for every subsystem. Cross-file timestamp matching is gone — the old files did not even share a clock (`wanted-trace` was stamped 77359 while `map-recenter` read 424281 in the same session).
- Bounded: 8 MB hard cap, rotates to `GameplayTweaks.log.1`.
- `[Logging] Verbose=0` by default. TRACE (per-tick/per-scan detail, e.g. the reserve/Dead Eye sample) is suppressed; INFO/WARN/ERROR always emit.

Deliberately preserved, because these properties found real bugs today:
- **Idle heartbeats are INFO, never TRACE**, so "the log is silent" still means "not running".
- **Every field name kept byte-for-byte.** `focusWrites=` beside `frames=` found the per-frame freeze; `owned=1` settled Lexer-Lux/Lexeditor#164; `hb hook` vs `hb script` settled Lexer-Lux/Lexeditor#114/#117. `pause_map_zoom` keeps both heartbeats as separate call sites with their distinct field sets.

Not converted, deliberately: `writeCatalogEffectProbe()` still writes `GameplayTweaks.catalog-effects.log`. It is a one-shot developer data dump, not diagnostics, and it is a report format rather than an event stream.
