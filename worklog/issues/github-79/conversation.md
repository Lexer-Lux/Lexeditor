# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5311976419 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79

Created: 2026-09-01T12:44:24Z; updated: 2026-09-04T12:25:10Z

Exact metadata: [source record](sources/issue-5311976419-019a517f1ff2efecfd2bf533a31ef31b986a3946fa588620e7ecbedd45a88048.json).

Nearly every tab in the FF7 (Original) plugin renders the "not integrated" state rather than editable data — Characters, Encounters, Enemies and most others. The tab styling is fine; the datasets behind them are not wired up.

Work needed:
- Audit which FF7 datasets have a proved editable source (kernel.bin sections already partly handled in `games/ff7/kernel.py`) and which do not.
- For each tab, either integrate the real format or make the tab honestly report what is missing and what would unlock it, in line with the FF9 plugin's "no proved editable source" card.
- Follow the project rule that every plugin exposes a Data Map screen, and keep list/detail structure consistent with the RDR2 plugin.

Not a priority; expected to be expensive.

## issue 5311976419 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79

Created: 2026-09-01T12:44:24Z; updated: 2026-09-06T13:31:03Z

Exact metadata: [source record](sources/issue-5311976419-1b6504217dc201c4136d04e0f514f4b46fe5f6678c10a202197214464ebcaeab.json).

**Actionable — partly implemented.** Unmerged PR #359 adds starting-character stats, limit-learning fields and safer project saves for both editions. Starting stats do not rewrite existing saves.

Enemies, encounters, shops and wider character/text editing remain unfinished. Integration and in-game validation are still needed; the Characters work alone is not complete FF7 support.

## issue 5311976419 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79

Created: 2026-09-01T12:44:24Z; updated: 2026-09-06T13:31:03Z

Exact metadata: [source record](sources/issue-5311976419-f79c08e013292959dca2b590017e80f2479288d3828f71c6178c0cdbea8aae29.json).

**Actionable — partly implemented.** Unmerged PR #359 adds starting-character stats, limit-learning fields and safer project saves for both editions. Starting stats do not rewrite existing saves.

Enemies, encounters, shops and wider character/text editing remain unfinished. Integration and in-game validation are still needed; the Characters work alone is not complete FF7 support.

## comment 5559373025 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79#issuecomment-5559373025

Created: 2026-09-06T12:58:50Z; updated: 2026-09-06T12:58:50Z

Exact metadata: [source record](sources/comment-5559373025-d84795ad694041a52beb875ac5a1bc3720745331571f98709aee434a848d52ca.json).

PR #359 adds Characters starting stats and limit-learning fields for both FF7 editions, safer project saves, and independent tab loading. Enemies, encounters and shops remain unimplemented; their tabs now explain the missing work. Not yet merged or tested in game.

After checking out the PR separately from the FF8 work:
- [ ] Open each FF7 edition; confirm nine named Characters slots and working equipment/materia tabs.
- [ ] In a disposable mod project, change Strength by 1, save/reopen, confirm persistence, then restore it. Vanilla and the installed kernel must stay unchanged.
- [ ] Check Enemies, Encounters, Shops and Data Map for specific status explanations. Report the edition and a screenshot for blank tabs, incorrect names or save errors.
