# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356288606 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120

Created: 2026-08-06T01:57:12Z; updated: 2026-09-05T06:55:53Z

Exact metadata: [source record](sources/issue-5356288606-e6afc1f6b5ab191d1ff1eb106fd28eb4fd9c239b179e04a5ed4310c789d31db9.json).

Flag when compiling the mod that enables/disables certain features.

## issue 5356288606 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120

Created: 2026-08-06T01:57:12Z; updated: 2026-09-06T13:07:04Z

Exact metadata: [source record](sources/issue-5356288606-f9c2f1e57982f77a0cdc7d9ff78a429b2d74a7b8cbe5c74a886f6189f5d5e7bb.json).

**Status: Installed; needs your check.** Development readouts share one tilde toggle. The obsolete separate ShowMode setting is removed.

- [ ] Start the development build in Story Mode. Press tilde once: all development readouts should hide; press again and they should return together.
- [ ] Check that Stamina no longer exposes a separate ShowMode setting. Report a readout that ignores the toggle or an obsolete control that remains.

## issue 5356288606 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120

Created: 2026-08-06T01:57:12Z; updated: 2026-09-06T13:57:19Z

Exact metadata: [source record](sources/issue-5356288606-ca9e379f51ac9b20dace98334d903e7a76ba1d292fe1e85d4701f1da83569db2.json).

**Status: Installed; needs your check.** Development readouts share one tilde toggle. The obsolete separate ShowMode setting is removed.

- [ ] Start the development build in Story Mode. Press tilde once: all development readouts should hide; press again and they should return together.
- [ ] Check that Stamina no longer exposes a separate ShowMode setting. Report a readout that ignores the toggle or an obsolete control that remains.

## comment 5550114750 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120#issuecomment-5550114750

Created: 2026-08-06T06:17:30Z; updated: 2026-08-06T06:17:30Z

Exact metadata: [source record](sources/comment-5550114750-acf732a568614e6ac175d29993b7d4518d96428979901a50ba9ca51a5b4e2e61.json).

Implemented compile-time Dev Mode. Normal builds force probes/debug markers/traces off regardless of stale INI values; build-dev.bat explicitly enables them while reusing the authoritative build. Both dev and release builds pass, with a final release build queued for installation. Keeping actionable until it lands.

## comment 5550114766 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120#issuecomment-5550114766

Created: 2026-08-06T12:28:32Z; updated: 2026-08-06T12:28:32Z

Exact metadata: [source record](sources/comment-5550114766-17b6189edf98fb7c7c73c0349b85c9cb50c34689ce278e846e24f5d332f5f356.json).

make it so when the mod is compiled as a dev, i can hit the tilde/~ button to toggle dev mode at will.

## comment 5550114776 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120#issuecomment-5550114776

Created: 2026-08-06T13:27:06Z; updated: 2026-08-06T13:27:06Z

Exact metadata: [source record](sources/comment-5550114776-4e41eb35e186e41d0b63bbd2c681d609f35e3357d5ea250a34aa60430bfe3cea.json).

Installed as an explicit development build, SHA-256 F1A98C615AB3D0B4D1DB0BD4520144D789F51CF5F84C495C2E595D5452CF3B96. Press backtick/tilde twice in game. Confirm the feed shows Developer mode disabled, then Developer mode enabled, and GameplayTweaks.dev-mode.log records enabled=0 followed by enabled=1. A normal release build intentionally compiles this handler out.

## comment 5550114783 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120#issuecomment-5550114783

Created: 2026-08-11T06:23:25Z; updated: 2026-08-11T06:23:25Z

Exact metadata: [source record](sources/comment-5550114783-b2bd4be0509966b2e9d25b13c5173f68dbf659fb9d7c14836653f5552f92657b.json).

The release build was not a valid non-development baseline: normal prone entry was unavailable. Dev mode must control only authoring tools, editor controls, and diagnostics; it must never decide whether a gameplay feature is dispatched. The current source reads Prone.Enabled independently and gates only Prone.DevelopmentTrace, but the release artifact did not preserve that behavior. I am adding a dev/release gameplay-parity check before another build.

## comment 5550114790 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120#issuecomment-5550114790

Created: 2026-08-11T08:45:51Z; updated: 2026-08-11T08:45:51Z

Exact metadata: [source record](sources/comment-5550114790-92aa8108784bced8f16ba0cb81e9c8d31b89f3a1aa647547430c12e818acf05e.json).

The current development build keeps the Tilde toggle and starts with development mode enabled. Dev mode now controls only authoring tools, editor controls, and diagnostics. Prone, climbing, dodge roll, and other gameplay dispatch are outside every development gate.

The development build is installed. Test Tilde off and on, then enter prone in both states. Camera editing should disappear only while development mode is off; prone must work in both states.

## comment 5550114802 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120#issuecomment-5550114802

Created: 2026-08-20T10:31:16Z; updated: 2026-08-20T10:31:16Z

Exact metadata: [source record](sources/comment-5550114802-a50269c6f59ab4e9c2100897abfe2ee40a657fc414528842f4cc5c1c1c3a02b0.json).

New requirement: remove Stamina / Show Mode from both settings surfaces and from the INI. The stamina mode readout must follow the one shared development-mode latch directly: a development build starts with it visible, and Tilde hides or restores it with the other developer tools. There must be no separate saved toggle.

## comment 5550114816 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/120#issuecomment-5550114816

Created: 2026-08-20T10:36:20Z; updated: 2026-08-20T10:36:20Z

Exact metadata: [source record](sources/comment-5550114816-d81e904cd17f6c23c7fca68de625d66dbb4527bc14cff261aa0621c7f5e6b30b.json).

Installed. Stamina / Show Mode is gone from the INI, LEXEDITOR, and the in-game settings menu. The player/horse stamina mode readout now follows the shared development-mode latch directly. In this development build it should be visible at startup; press Tilde once and it must disappear, then press Tilde again and it must return. There is no separate saved toggle.
