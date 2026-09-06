# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356319385 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/249

Created: 2026-08-10T14:58:35Z; updated: 2026-09-05T07:02:52Z

Exact metadata: [source record](sources/issue-5356319385-83d5627807b8f9a68ac2b7503147ddb0b57e37fb917f4e1921886c9015785a03.json).

Going from holding run to not holding it should take you from sprinting to walking. Instead it takes you back to running, like in vanilla. The specifications of the rework implicitly required you to fix this. You didn't. I explicitly asked you to fix this. You didn't. How many times must I ask you?

## issue 5356319385 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/249

Created: 2026-08-10T14:58:35Z; updated: 2026-09-06T13:18:08Z

Exact metadata: [source record](sources/issue-5356319385-b646074bbe72260a4bd957ad171144ce3b512dfdd2e4433eb035bbcf68f31faa.json).

**Status: Closed after the installed transition correction.** Releasing Shift while still moving should return directly to walking, without a persistent or intermediate run. Remaining location-specific sprint restrictions are tracked in #236.

## comment 5550149724 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/249#issuecomment-5550149724

Created: 2026-08-10T17:23:54Z; updated: 2026-08-10T17:23:54Z

Exact metadata: [source record](sources/comment-5550149724-71f129bd86df2baead494aeb1285e4a24a56ed6b2faf64c18b55868f5b58b704.json).

The direct sprint-to-walk candidate is installed and enabled. On Shift release it suppresses Sprint before applying the walk ceiling, retains release ownership until three consecutive moving frames read no running/no sprinting with walk blend, and logs the very first owned frame rather than hiding an intermediate run. Hold W+Shift, keep holding W, and release Shift repeatedly; the first continuing-movement frame must visibly be walk, not a brief or sustained vanilla run.
