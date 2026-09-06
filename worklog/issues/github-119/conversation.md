# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356288308 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/119

Created: 2026-08-06T01:56:32Z; updated: 2026-09-05T06:55:49Z

Exact metadata: [source record](sources/issue-5356288308-9e82a645c93127f16423674723308365b1fedc0ce9abd8ee5bb84ddfbf8b3bc8.json).

Like in Ubisoft games. Or MSGV. Req. Lexer-Lux/Lexeditor#113 

## issue 5356288308 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/119

Created: 2026-08-06T01:56:32Z; updated: 2026-09-06T12:46:32Z

Exact metadata: [source record](sources/issue-5356288308-7c1a318c624ddadc590b5f42be5bf12d7c50b01d48bc90025d200ca5116cfd1b.json).

Show clear directional detection feedback without inventing a universal awareness percentage.

**Status: A discrete-state prototype was installed, but the supporting stealth audit in #113 is still incomplete.** Finish the remaining evidence and prepare a controlled observer test before calling the requested indicator behavior ready.

## issue 5356288308 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/119

Created: 2026-08-06T01:56:32Z; updated: 2026-09-06T13:57:19Z

Exact metadata: [source record](sources/issue-5356288308-84cf89073c4aeac70b6f0a28fe9da9ba74d6e1f3445e7e19ae4bb1a2f39ae711.json).

Show clear directional detection feedback without inventing a universal awareness percentage.

**Status: A discrete-state prototype was installed, but the supporting stealth audit in #113 is still incomplete.** Finish the remaining evidence and prepare a controlled observer test before calling the requested indicator behavior ready.

## comment 5550114375 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/119#issuecomment-5550114375

Created: 2026-08-06T06:27:22Z; updated: 2026-08-06T06:27:22Z

Exact metadata: [source record](sources/comment-5550114375-fb3bd33910a30bb0c33587273a805316fe72adbbbd316d9245dccfe10261386f.json).

Implemented discrete vanilla-style directional indicators without a fabricated percentage: ivory focused hostile LOS, amber targeted suspicion/agitation, red combat, capped/faded and suppressed in menus/cinematics. Combined release build passes; installation is queued, so this remains actionable until it lands.

## comment 5550114385 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/119#issuecomment-5550114385

Created: 2026-08-06T12:41:53Z; updated: 2026-08-06T12:41:53Z

Exact metadata: [source record](sources/comment-5550114385-1f690fb21097ed085eacee91d5198910bd185475e62a11ae7db01b13d40494d5.json).

Correction: this implementation was attempted prematurely while Lexer-Lux/Lexeditor#119 was explicitly blocked by unfinished Lexer-Lux/Lexeditor#113. That means it was not eligible for implementation or testing. The existing code is not being presented as accepted work. Lexer-Lux/Lexeditor#119 is restored to `actionable` and remains blocked by Lexer-Lux/Lexeditor#113; no further work on it should occur until that dependency is actually completed.

## comment 5550114396 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/119#issuecomment-5550114396

Created: 2026-08-06T13:27:02Z; updated: 2026-08-06T13:27:02Z

Exact metadata: [source record](sources/comment-5550114396-108228b600223b2cc9b322b123b5f7c87df43e59c4d88628ace0782d6e09bf3a.json).

The stealth audit dependency is complete and the blocker has been removed. Installed in development build F1A98C615AB3D0B4D1DB0BD4520144D789F51CF5F84C495C2E595D5452CF3B96. This is FC3-style discrete directional feedback, not a fabricated MGSV percentage: ivory = hostile has immediate perception + affirmative visibility + LOS; amber = targeted suspicion/agitation or an actual player-aimed flee/threat response; red = combat. Test standing, crouched, walking, running, and sprinting around one hostile; stance/movement should alter the AI outcome, never disable the HUD itself. Break LOS and confirm the indicator briefly holds/fades. Ordinary civilian glances should not clutter the display; pause/satchel/death/fade must hide it; maximum four.
