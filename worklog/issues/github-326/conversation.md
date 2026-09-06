# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356486282 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/326

Created: 2026-09-04T06:51:17Z; updated: 2026-09-05T13:30:15Z

Exact metadata: [source record](sources/issue-5356486282-ef6e3ee5cc329c1b4139931a6ed8e3d2549e712990d42ad1c806b49e74bb0f92.json).

Lexer's request:\n\n> tweak that just removes the damage limit.\n\nThe supported executable has a native 60,000 Break Damage Limit path. The implementation uses that proved path instead of inventing a wider storage type.

## issue 5356486282 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/326

Created: 2026-09-04T06:51:17Z; updated: 2026-09-06T12:59:59Z

Exact metadata: [source record](sources/issue-5356486282-4676196bfc1928271ad482eae8a3f8d122e09c0a005851ec2c560e58b26edd81.json).

**Status: Implemented as a higher cap, not unlimited damage.** The current patch raises the normal 9,999 clamp to the game’s existing 60,000 path; it has not been accepted in battle.

Prepare a known ordinary damage/healing case that exceeds 9,999 and identify the delivered build before requesting a test. Full removal of every limit is not what the current implementation provides.

## issue 5356486282 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/326

Created: 2026-09-04T06:51:17Z; updated: 2026-09-06T12:59:59Z

Exact metadata: [source record](sources/issue-5356486282-77747f0b25531d1d957d4674ae9f46b3a6457572f119b904aaf5f7f6d1a754c1.json).

**Status: Implemented as a higher cap, not unlimited damage.** The current patch raises the normal 9,999 clamp to the game’s existing 60,000 path; it has not been accepted in battle.

Prepare a known ordinary damage/healing case that exceeds 9,999 and identify the delivered build before requesting a test. Full removal of every limit is not what the current implementation provides.

## comment 5550347325 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/326#issuecomment-5550347325

Created: 2026-09-04T16:32:45Z; updated: 2026-09-04T16:32:45Z

Exact metadata: [source record](sources/comment-5550347325-655844a1878c617468be1290f3f18e3358e1e6051b1412651dd4890b638fea32.json).

The Tweak is implemented and defaults off. It changes FF8's final global damage clamp to use the game's existing Break Damage Limit path for every action, raising the normal 9,999 cap to the engine's proven 60,000 cap without changing damage calculation or sign handling. The executable and generated-patch checks pass. Please confirm ordinary attacks and healing above 9,999 in battle.
