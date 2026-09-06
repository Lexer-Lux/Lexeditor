# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356324138 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/265

Created: 2026-08-11T02:07:56Z; updated: 2026-09-05T07:03:43Z

Exact metadata: [source record](sources/issue-5356324138-4cf4ed177035ab368059bf8085869efd65c3a36e152c8d7f741ee7bd131240be.json).

Mash SPACE To do rolls in quick succession and you'll see the 1st costs stamina but the 2nd doesn't.

## issue 5356324138 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/265

Created: 2026-08-11T02:07:56Z; updated: 2026-09-06T13:18:25Z

Exact metadata: [source record](sources/issue-5356324138-b135d408694c90a0ab03cddc4f57cd2b4c367fc98830c01eceb7653bdc3b1148.json).

**Status: Closed after the rapid-input correction.** Each accepted roll receives one stamina charge even when rolls are requested in quick succession. Overall dodge input and delivery work remains in #106.

## comment 5550155645 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/265#issuecomment-5550155645

Created: 2026-08-11T09:32:37Z; updated: 2026-08-11T09:32:37Z

Exact metadata: [source record](sources/comment-5550155645-8f98e66f18b534cf536e9c14631ad0fe6f959e6938f1de0b5637a0a8ae8b6a27.json).

Rapid roll requests are now sampled before the active-phase return and queued through the current P2 phase. Every accepted P1 has one sequence number, one stamina charge through the shared stamina controller, and a 250 ms persistence readback. Test two rapid rolls and compare the two visible bar reductions.
