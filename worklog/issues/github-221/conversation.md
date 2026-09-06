# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356312516 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/221

Created: 2026-08-06T18:58:13Z; updated: 2026-09-05T07:01:17Z

Exact metadata: [source record](sources/issue-5356312516-39ae3f9d15fa12f582a11e82686cb09a0ed2026ac37d3376cd9e26d1a93ecaeb.json).

Aiming a weapon and entering Dead Eye for long enough crashes the game to Rockstar generic `ERROR:FFFFFFFF / Unknown error FFFFFFFF` dialog. Reported 2026-08-06 ~12:41 in Annesburg on dev build `9703EA02...`.

## Why there is no evidence yet

`script.cpp` already installs a vectored crash tracer (`gameplayTweaksCrashTrace`) that records fatal first-chance exceptions with the current update stage, precisely so the FFFFFFFF dialog can be attributed. Two defects made it useless here:

1. **The trace was deleted on startup.** `DeleteFileA(g_crashTracePath)` ran at init, so relaunching the game after a crash destroyed the only record of the run that crashed. A crash is always reported after a restart, so this guaranteed zero evidence every time. `ScriptHookRDR2.log` confirms the pattern — its session begins 12:43:19, after the 12:41 crash, and holds no crash entry.
2. **No stage markers covered the suspect code.** `CRASH_TRACE_STAGE` calls stopped at line 1995; the entire reserve/stamina/Dead Eye block (~2000-2450) had none, so any crash there would have reported a stale, misleading stage name.

## Fixed in this build

- Previous run is preserved as `GameplayTweaks.crash-trace.prev.log` instead of deleted. **That is the file to read after a crash.**
- Added stages `coreClock`, `deadeyeReserve`, `deadeyeExhaustionLatch`, `reserveTrace`.
- `GameplayTweaks.reserve.log` was append-only with no truncation and had reached 5.8 MB / 41645 lines of cross-session history; it now restarts once per launch.

## Leading suspect, not yet confirmed

The Lexer-Lux/Lexeditor#176 exhaustion latch (`script.cpp` ~2179-2200) calls `SET_DEADEYE_DISABLED` and `DEACTIVATE_SPECIAL_ABILITY` on the ability while it is active, and re-asserts every tick while latched. Holding Dead Eye until the outer ring empties is exactly the "long enough" condition, and the last reserve log shows `deadeye=143.897` — above 100, so the overfilled/fortified path is involved. This is a hypothesis, NOT a diagnosis; the trace will confirm or refute it.

Built SHA-256 `CFFA7ACC1623E4512D9C11D10A14A527D8100C0F55C0B409A302CA1A24236A32`, install queued behind the running game.

## Repro to capture evidence

- [ ] Aim and hold Dead Eye until it crashes again.
- [ ] Relaunch, then attach `GameplayTweaks.crash-trace.prev.log` — its `stage=` field names the block.

Note: `Banking.asi`, `CoreRankRepair.asi`, `LessMoney.asi`, `Rampage.asi` and `UWO.asi` are also loaded, so the trace `module=` field is needed to confirm the fault is ours at all.

## issue 5356312516 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/221

Created: 2026-08-06T18:58:13Z; updated: 2026-09-06T13:17:49Z

Exact metadata: [source record](sources/issue-5356312516-c50eccc8e0b1b940507802d8d16c870ce608ad0f735cb7d3d4a6983c72b0008b.json).

**Status: Closed crash report; no final cause is documented here.** Crash-trace retention and missing stage markers were repaired. The exhaustion latch remained a hypothesis, not a diagnosis, and the old queued build/test request is not a current instruction to reproduce a crash.
