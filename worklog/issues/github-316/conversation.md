# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356484601 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/316

Created: 2026-08-29T09:38:54Z; updated: 2026-09-05T07:39:46Z

Exact metadata: [source record](sources/issue-5356484601-419df3d9e3eda64d28c599678b0bd3660c324ac865a668fda94391507e8b283c.json).

Add an FF8 gameplay rule for flying enemies.

- Settings includes a bounded `Flying EVA Bonus (%)` control.
- Enemies with the game's flying property gain this effective EVA bonus.
- Ranged physical attacks ignore only the added flying bonus.
- A melee attacker under Float also ignores only the added flying bonus.
- Normal enemy EVA still applies.
- Magic remains unchanged unless the original attack data classifies it as physical.
- Do not assume that a 255 or nominal 100% hit-rate attack should bypass this rule. First inventory which attacks use those values and preserve only a proven engine exception. Common physical attacks must not make the rule pointless.

Implement this through the managed FFNx runtime path. Use named/bounded controls and show the effective calculation in LEXEDITOR. Static patch generation is not in-game acceptance.


## issue 5356484601 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/316

Created: 2026-08-29T09:38:54Z; updated: 2026-09-06T12:59:39Z

Exact metadata: [source record](sources/issue-5356484601-58f03d66abc033aea11cc6c6cf15863ff564c38d308924afa195250fac6b7532.json).

Flying enemies gain the configured evasion bonus against melee; ranged attacks and Float ignore only that bonus. The patch deliberately routes gunblade hit-rate 255 through ordinary accuracy rather than bypassing the rule.

**Status: A generated patch exists, but patch-load and battle results remain unverified.** Prepare fixed enemy/stat/attack comparisons, including ranged and Float controls, before asking you to judge random hits and misses.

## issue 5356484601 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/316

Created: 2026-08-29T09:38:54Z; updated: 2026-09-06T12:59:39Z

Exact metadata: [source record](sources/issue-5356484601-910d4a00bc495faaa8d5eee91f2ef4626783aee0e4cb25d8e7c7aa61daede5ed.json).

Flying enemies gain the configured evasion bonus against melee; ranged attacks and Float ignore only that bonus. The patch deliberately routes gunblade hit-rate 255 through ordinary accuracy rather than bypassing the rule.

**Status: A generated patch exists, but patch-load and battle results remain unverified.** Prepare fixed enemy/stat/attack comparisons, including ranged and Float controls, before asking you to judge random hits and misses.

## comment 5550345481 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/316#issuecomment-5550345481

Created: 2026-08-29T09:50:32Z; updated: 2026-08-29T09:50:32Z

Exact metadata: [source record](sources/comment-5550345481-3540846def568a2dc460adae5d1eb54b57cc076ba01ff88a59381ff1ab73d5ba.json).

The installed data answers the accuracy concern: 100 is an ordinary hit-rate value, while 255 is FF8's special always-hit value. Irvine, Rinoa, and Laguna ranged weapons use ordinary values near 100, so they do not bypass the flying rule. The real exception is Squall: every gunblade uses 255. Preserving vanilla perfect accuracy would exempt Squall's regular attacks; making the flying bonus override 255 for melee would make ranged attacks and Float more distinct, but would intentionally nerf Squall against flying enemies.

## comment 5550345492 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/316#issuecomment-5550345492

Created: 2026-08-29T10:42:47Z; updated: 2026-08-29T10:42:47Z

Exact metadata: [source record](sources/comment-5550345492-dcf4b185c8bca8c5e264f8e64c3b15fd7039cf4e9d0de03abd20d21c28d95576.json).

The generated Hext patch now routes hit rate 255 through normal accuracy. Intrinsic flying enemies receive the configured EVA bonus against ordinary melee attacks; ranged attacks and Float-enabled melee attacks ignore only that bonus. Managed FFNx is installed, so the remaining check is the FFNx patch-load log and an in-battle hit/miss check.
