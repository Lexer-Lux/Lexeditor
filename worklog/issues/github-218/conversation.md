# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356311726 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218

Created: 2026-08-06T14:48:08Z; updated: 2026-09-05T07:01:08Z

Exact metadata: [source record](sources/issue-5356311726-6e0464bd3ab30e4bdf101b00326a61a3d98ccd55077a9871cc8532fac7c3c7cf.json).

Let me set, in the settings, the rate at which Deadeye points are consumed in deadeye mode, in points/sec.

## issue 5356311726 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218

Created: 2026-08-06T14:48:08Z; updated: 2026-09-06T13:17:46Z

Exact metadata: [source record](sources/issue-5356311726-7dedb282d00befb1a3fe1e7f90f8455136d0ae9e65681dac07dce85d9e8d7fed.json).

**Status: Closed as implemented.** Dead Eye Drain Rate is exposed consistently in the editor, in-game settings and INI, with live reload and a 1–100 points/s range. Zero means the game’s default, not zero consumption, so it is not offered as an unlimited mode.

## comment 5550140835 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140835

Created: 2026-08-10T06:26:42Z; updated: 2026-08-10T06:26:42Z

Exact metadata: [source record](sources/comment-5550140835-103bbef3a8d37f5786ad5fa297e7cfd989c5c20f218d7575167f2b8c31bc896d.json).

Considering 0 and 99 feel the same I'm prety sure this does nothing.

## comment 5550140846 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140846

Created: 2026-08-10T07:17:17Z; updated: 2026-08-10T07:17:17Z

Exact metadata: [source record](sources/comment-5550140846-5ba3a6558db94993c71a4fe897910bc461e20653b3eb8b880e791ad56b156b31.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test the configured Dead Eye points-per-second drain and zero drain while inactive.

## comment 5550140857 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140857

Created: 2026-08-10T07:56:34Z; updated: 2026-08-10T07:56:34Z

Exact metadata: [source record](sources/comment-5550140857-c31ee8d969efb9ed344449e62da0b5a0b15177c8a5437363d10c07773ad866c6.json).

Using -25 results in it continuing to DRAIN when used, but at some unknown rate.
What is clamping it? Tell me.
Find the values, and make sure that whatever is clamping it is reflected in the value input. You shouldn't be able to put in misleading or untrue values into the settings. That applies for every setting. If a value below 0 becomes 0 ingame, then values entered below 0 should become 0 too.

## comment 5550140867 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140867

Created: 2026-08-10T10:45:23Z; updated: 2026-08-10T10:45:23Z

Exact metadata: [source record](sources/comment-5550140867-0a1d00c2be3f257e41d5f8d2237a03d026b02e6c14490738411e02295f246786.json).

deadeye drain is at 0 but still draining so i think it's safe to say you totally failed this one too.

## comment 5550140884 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140884

Created: 2026-08-10T19:00:42Z; updated: 2026-08-10T19:00:42Z

Exact metadata: [source record](sources/comment-5550140884-81823e76297e0616544e6fe3be169b48556006440661af9976ba32bcab6d5861.json).

this is getting ridiculous.

## comment 5550140895 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140895

Created: 2026-08-10T23:45:43Z; updated: 2026-08-10T23:45:43Z

Exact metadata: [source record](sources/comment-5550140895-b3a1e298144cb363facf804bbf21dc89d21b3e8500c40ccf7595c55799fe7d53.json).

Installed the zero-rate correction. While Dead Eye is active, 0 points/second now submits an exact zero duration cost every frame instead of returning to vanilla drain. Set the rate to 0 and confirm the bar does not drain.

## comment 5550140912 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140912

Created: 2026-08-11T01:03:58Z; updated: 2026-08-11T01:03:58Z

Exact metadata: [source record](sources/comment-5550140912-c68a0802b9aa91cc1dcc289871f4f3d51cc29217118c4eea5126149e5edbb762.json).

Still not working. Being set to 1 seems to work fine, so it seems clamped. Why not clamp the input at 1-99 or something?

## comment 5550140920 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140920

Created: 2026-08-11T01:45:57Z; updated: 2026-08-11T01:45:57Z

Exact metadata: [source record](sources/comment-5550140920-64249195a3bb5908bfc921a4e26f6c4f62791cc20f0c011cd2b8c993fc340aa3.json).

The value 0 is Rockstar's default sentinel, not a zero-drain rate. The setting now accepts 1 through 100 only; 1 is the slowest supported drain. Existing 0 values are normalized to 1.

## comment 5550140937 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/218#issuecomment-5550140937

Created: 2026-08-12T23:21:53Z; updated: 2026-08-12T23:21:53Z

Exact metadata: [source record](sources/comment-5550140937-de52d77afab56fcc5e8e155fe63db3b62d0c763cdd2780aa7504218d4e075c6e.json).

This is already wired end to end — verified each layer:

- **INI**: `[DeadEye] ConsumptionPointsPerSecond` (`GameplayTweaks.ini:240`), hot-reloads.
- **Read + clamp**: `script.cpp:1156-1163`, clamped to 1.0–100.0, and an out-of-range value is normalized back into the INI so the file never shows a value the engine won't use.
- **Applied**: `SET_DEADEYE_DURATION_COST(player, g_deadeyeConsumptionRate)` at `script.cpp:636` — it drives the real native, not a cosmetic value.
- **Settings menu**: "Cores › Dead Eye › Dead Eye Drain Rate", unit `points/s`.
- **Editor**: same key, matching range 1.0–100.0 step 0.1, so the editor cannot show a value the engine would silently clamp.

One thing worth knowing, and it's why the range starts at 1 rather than 0: the game treats **0 as its default drain**, not as "no drain". So 0 does not mean infinite Dead Eye — the minimum meaningful rate is 1 point/sec.

Closing as implemented. Reopen if the in-game rate doesn't track the value you set.
