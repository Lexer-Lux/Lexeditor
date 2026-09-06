# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356489074 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/340

Created: 2026-08-24T16:26:46Z; updated: 2026-09-05T07:40:52Z

Exact metadata: [source record](sources/issue-5356489074-21646c0e48ca1dce8df1e4a4152c9439b6ed72cff7f1a07d4778a494030eae22.json).

Add a persistent top-right HUD for money and ammunition. Show money as "$X" with no "Money" label. Put the current weapon ammunition count directly below it. Read money and ammunition from named RDR game state and use RedHook's supported custom-rendering path. Acceptance: the HUD remains present during normal play, money updates after a transaction, ammunition updates after firing, reloading, and changing weapons, and the values and alignment are player-visible and correct at multiple resolutions.

## issue 5356489074 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/340

Created: 2026-08-24T16:26:46Z; updated: 2026-09-06T13:07:50Z

Exact metadata: [source record](sources/issue-5356489074-9ab38738443bfa828f6fd91789ca0e6185ff0c6b2bcb04eb7dc535c1f4d6bf75.json).

**Status: A repaired build is installed; needs your check.** Money should show as $X above ammunition, only during normal gameplay—not loading. Avoid the weapon-wheel crash in #333.

- [ ] Restart RDR1 and load Story Mode. Confirm no custom money/ammo text appears during loading, then check the money value against your actual balance.
- [ ] Make one purchase and fire/reload the equipped gun without opening the wheel. Confirm money and ammunition update and the text stays stable.
- [ ] Report an incorrect value, flicker or bad placement with a screenshot and your display resolution.

## comment 5550350599 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/340#issuecomment-5550350599

Created: 2026-08-24T17:02:41Z; updated: 2026-08-24T17:02:41Z

Exact metadata: [source record](sources/comment-5550350599-313053c4240c52ecf99a363b0c43227f6e7ad1daa8013beba5afbad8c90f6d48.json).

The runtime now draws a permanent right-aligned `$X` line and a loaded/reserve ammunition line below it. Position and scale are editable in LexerRDR.ini and the Lexeditor Settings tab. Both builds pass; in-game placement and live transaction, firing, reload, and weapon-change updates still need confirmation after RedHook is installed.

## comment 5550350611 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/340#issuecomment-5550350611

Created: 2026-08-27T05:50:32Z; updated: 2026-08-27T05:50:32Z

Exact metadata: [source record](sources/comment-5550350611-168892b6316e3afd215b7cd065f8281b0f7e76fad44b38977966c8816467e9ae.json).

Runtime check failed: the custom HUD starts during the game-mode loading screen, flickers through invalid values, and then shows a bare 0 in play despite a cash balance above . Gate it to the normal gameplay HUD/radar visibility window, and fix the live value and currency formatting.

## comment 5550350623 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/340#issuecomment-5550350623

Created: 2026-08-27T06:17:32Z; updated: 2026-08-27T06:17:32Z

Exact metadata: [source record](sources/comment-5550350623-d846af953d074fda121b0fb1b5cb1a3f3996fd2ec3db0ec89be9e2157d615c1c.json).

Installed the repaired development plug-in. The money and ammo text now waits for a valid player and a visible minimap, reads the cash value from the correct array element, and keeps its text alive for RedHook rendering. Please confirm that no text appears during loading, the value includes `$` and matches your cash, and the ammo line stays stable.
