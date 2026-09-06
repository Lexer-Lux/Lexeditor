# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356287172 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/115

Created: 2026-08-06T01:51:00Z; updated: 2026-09-05T06:55:33Z

Exact metadata: [source record](sources/issue-5356287172-63796cae9ff638b7fdf5624622490c01043c81f253700ba4910bf8862debea0c.json).

Goes Level 0-10. Start at 0, each level up is for future Gambler Challenge rework levels. Let me set amounts in the .ini. I think the TODO.txt contains tentantive amounts I want. I think there was a mod with a similar feature mentioned at some point, in case reference is needed?

## issue 5356287172 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/115

Created: 2026-08-06T01:51:00Z; updated: 2026-09-06T13:17:08Z

Exact metadata: [source record](sources/issue-5356287172-2a6bc2471c5c2919ca5620af42dadb73e5c71a3cc64f4c63d1d2076df4ee362e.json).

**Status: Closed after the wallet-cap implementation.** Gambler ranks 0–10 select independently configurable limits. Auto-Bank, over-cap sale behavior and wallet feedback remain tracked in #208 rather than being implied complete here.

## issue 5356287172 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/115

Created: 2026-08-06T01:51:00Z; updated: 2026-09-06T13:53:55Z

Exact metadata: [source record](sources/issue-5356287172-dd42c549083ffd0d488b0d5072c8565616483557beafc780276c422b444b0c7c.json).

**Status: Closed after the wallet-cap implementation.** Gambler ranks 0–10 select independently configurable limits. Auto-Bank, over-cap sale behavior and wallet feedback remain tracked in #208 rather than being implied complete here.

## comment 5550112958 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/115#issuecomment-5550112958

Created: 2026-08-06T02:46:24Z; updated: 2026-08-06T02:46:24Z

Exact metadata: [source record](sources/comment-5550112958-3e2e8169d95154d861334e91671baaee05c48eca303492d6ceae5101d0db72e6.json).

Built and installed for testing.

Added `[WalletCap] Enabled=1` plus hot-reloaded `Rank0Dollars` through `Rank10Dollars`. Defaults are the migrated values: $1 / $2 / $4 / $7.50 / $12.50 / $20 / $40 / $75 / $150 / $250 / unlimited. `0` means unlimited.

The existing cash observer applies any Pig-mask fence multiplier first, then removes balance above the active Gambler-rank cap and shows the rank/cap in the feed. Build passed with the two pre-existing C4838 warnings; source/installed ASI and INI hashes match.

Please test one ordinary cash gain above your current cap and, if practical, a Gambler rank transition.
