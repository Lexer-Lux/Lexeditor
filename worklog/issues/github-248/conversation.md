# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356319109 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/248

Created: 2026-08-10T14:57:10Z; updated: 2026-09-05T07:02:48Z

Exact metadata: [source record](sources/issue-5356319109-bcd111214735a706175742c5d748462bc3de8eda1148da6626f97c85b3e67771.json).

You never got rid of crouch running.

## issue 5356319109 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/248

Created: 2026-08-10T14:57:10Z; updated: 2026-09-06T13:18:06Z

Exact metadata: [source record](sources/issue-5356319109-2515dc01d0801f01c578554f813f19d71718106678e1d0f0db72453b2c550ac6.json).

**Status: Closed after the installed movement correction.** Crouched movement remains a crouch walk when Sprint is held or released, rather than entering the running gait. Later overall movement work remains in #236.

## comment 5550149355 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/248#issuecomment-5550149355

Created: 2026-08-10T17:23:51Z; updated: 2026-08-10T17:23:51Z

Exact metadata: [source record](sources/comment-5550149355-cea403b9ca54dcb0b94145683043637fecbfe2b7762e942e56a817dc0b0523d0.json).

The no-crouch-run candidate is installed and enabled. Crouch/stealth now wins before Shift handling, suppresses Rockstar's Sprint input, applies the crouch-walk ceiling, and records live running/sprinting/blend/speed postconditions. Test crouched movement in every direction while holding and releasing Shift; it must remain a smooth crouch walk with no sprint stamina mode.
