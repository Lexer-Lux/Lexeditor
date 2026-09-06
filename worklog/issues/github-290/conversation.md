# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356331532 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/290

Created: 2026-08-20T10:06:43Z; updated: 2026-09-05T08:09:11Z

Exact metadata: [source record](sources/issue-5356331532-c62b3e6b84c1e5895e917efc97ecdc2f063b64e249ab409225f0a5f013e45d26.json).

lantern range and brightness appear to do nothing. 9999 and 0 -- no visible difference

## issue 5356331532 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/290

Created: 2026-08-20T10:06:43Z; updated: 2026-09-06T12:57:13Z

Exact metadata: [source record](sources/issue-5356331532-6a832841e2f8a39200cf2b3b1d2e2cda128e83bb49d14912142f1dd0f345da80.json).

Brightness and range must visibly change the lantern’s light, including no light at zero brightness.

**Status: Still broken in your latest test.** A settings-cache/readback correction exists in source but was not built or installed. Deliver and verify the actual light result; saved numbers alone are not acceptance.

## comment 5550164704 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/290#issuecomment-5550164704

Created: 2026-08-20T11:19:27Z; updated: 2026-08-20T11:19:27Z

Exact metadata: [source record](sources/comment-5550164704-89f8155c731831370068d58c9212e7eda9139b1ea220d175e0bf2de9db87f0fa.json).

Installed repair: lantern Range and Brightness now reach the light without the old minimum clamps. Zero in either setting disables the script light; finite positive values are preserved up to 10000. Test zero first, then use clearly different positive range and brightness values and confirm visible reach and intensity changes.

## comment 5550164723 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/290#issuecomment-5550164723

Created: 2026-08-20T12:33:09Z; updated: 2026-08-20T12:33:09Z

Exact metadata: [source record](sources/comment-5550164723-0d40db66388ed9ce1d7c9b6cb95e941d2daf364728fcc39472703ae4d6173ae7.json).

The radial was not applying Range or Brightness. The live sequence was: 999/999 loaded while the lantern was off, then the radial turned it on; 1/99 later loaded while it stayed on, before any radial action. The confusing failures all occurred after Range became 0. Brightness then changed through several values, but zero range disabled the light every time. Later Range returned to 999 while the lantern was off, so the next radial use again appeared to apply it when it only turned it on. I fixed the misleading evidence: Range/Brightness now have one hot-reload owner, every observed change is recorded, and the log separately reports valid settings, radial state, actual player/horse drawing, and executed light-call count. The radial still only toggles the lantern. After the queued build installs, turn it on once and leave it on; test 10/1, 50/1, 50/10, then 0/10 without touching the radial. Each written change should apply within about 0.25 seconds while the game is ticking. If the game pauses while unfocused, the first possible reload is when you return.

## comment 5550164740 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/290#issuecomment-5550164740

Created: 2026-08-20T14:04:06Z; updated: 2026-08-20T14:04:06Z

Exact metadata: [source record](sources/comment-5550164740-85c4572ce6d716ddca9520344d30d3bf2d8410db039ad223b3e692f0a189807e.json).

The intermittent lantern settings were real. LEXEDITOR replaces the INI file, but the process profile cache was never cleared, so the 4 Hz reader could keep returning stale values. Offset completion also acknowledged newer edits that were never used by the active solve. Source now clears the cache, reads range/brightness/offsets as one revision, snapshots each placement request, and acknowledges only the revision it actually completed. It also records the first real light draw or zero-value no-draw result. Focused lantern checks pass. This has not been built or installed, so Lexer-Lux/Lexeditor#290 stays actionable.

## comment 5550491875 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/290#issuecomment-5550491875

Created: 2026-09-05T08:09:08Z; updated: 2026-09-05T08:09:08Z

Exact metadata: [source record](sources/comment-5550491875-7cf7e59f7fe6dceff93233ab7fa99efdd56d53ccb82975cd8e6539490cc7f21f.json).

brightness and range do nothing. 0 brightness even has brightness.
