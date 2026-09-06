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

## issue 5311976419 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79

Created: 2026-09-01T12:44:24Z; updated: 2026-09-06T15:01:17Z

Exact metadata: [source record](sources/issue-5311976419-4768021fee44e84a86e97690dfab70cfdd1308e313987d109176cc93c7ad27c4.json).

**Actionable — partly implemented.** Unmerged PR #359 adds starting-character stats, limit-learning fields and safer project saves for both editions. Starting stats do not rewrite existing saves.

Enemies, encounters, shops and wider character/text editing remain unfinished. Integration and in-game validation are still needed; the Characters work alone is not complete FF7 support.

## issue 5311976419 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79

Created: 2026-09-01T12:44:24Z; updated: 2026-09-06T15:15:01Z

Exact metadata: [source record](sources/issue-5311976419-2d2826a1f6d495afbac6b4acfce7da7096ccaa6d18c9993ea82547d5e6fc3e81.json).

**Actionable — partly implemented.** Unmerged PR #359 adds starting-character stats, limit-learning fields and safer project saves for both editions. Starting stats do not rewrite existing saves.

Enemies, encounters, shops and wider character/text editing remain unfinished. Integration and in-game validation are still needed; the Characters work alone is not complete FF7 support.

## issue 5311976419 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79

Created: 2026-09-01T12:44:24Z; updated: 2026-09-06T16:45:17Z

Exact metadata: [source record](sources/issue-5311976419-24044cd7b2819983a07b222bd573d33bcb29ca9a858b36af40946a81d40e4d2c.json).

**Implemented and merged — needs installed-game acceptance.** PR #359 was merged into `master` as `3e2d2b924ac299f085b7f568c2394419ea0b3b63`, including completion commit `613d2b73c51956d921a032341317d0d37a815feb`.

The previously missing editors are now connected: character/enemy/formation AI; character growth curves and bonuses; inline/default names; separate Cait Sith/Vincent recruitment data; field and world encounter tables, Yuffie thresholds and Chocobo ratings; enemy/attack/formation records; shops/prices; and all 18 English kernel2 text sections. Existing equipment/materia editors remain available. The page has 24 dataset categories plus FFNx, grouped into subtabs, with independent availability and verified project saves.

**Verification:** all current-head FF7 and shared CI jobs passed. FF7 runs 57 binary/HTTP tests on Windows and Linux plus ten Chromium scenarios, including actual shared controls, save/reopen, layout, sound dispatch and muting. The source artifact was downloaded and its 19 changed/new source/test files matched the locally tested versions by SHA-256. These are synthetic-data checks, not installed-game proof.

**Installed acceptance checklist:**
- [ ] Update the normal Lexeditor checkout to the merged master and run `tools\FF7-checks.cmd` for both installed editions. This reads installed data, writes only disposable temporary project copies, verifies readback/source hashes and emits a JSON report. Missing or unreadable datasets remain failures, not a full-success result.
- [ ] In a disposable mod, edit/save/reopen representative character, AI, enemy, formation, field/world encounter, shop, price and text values. Confirm original installed files remain unchanged.
- [ ] Validate deployed outputs and native editor behavior in the actual games. This environment did not perform deployment or gameplay acceptance.

Format limits remain explicit: initial values do not rewrite existing saves; unknown executable builds are refused; fixed AI pools and scene blocks reject overflow rather than corrupting data. This is encounter-table editing, not arbitrary field scripting, world geometry or terrain reassignment. Saving a project is not automatic deployment.

Current documentation and primary format references: `codex/ff7-data.md`. Earlier recovery comments are historical: their missing-editor lists have been implemented by the completion pass. This issue remains open for the acceptance checks above, not because those editors are still absent.

## issue 5311976419 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79

Created: 2026-09-01T12:44:24Z; updated: 2026-09-06T16:45:17Z

Exact metadata: [source record](sources/issue-5311976419-4ade731ddfa45b2057b17eca20dde1160249de071353106cc3f67db99ec8e6bb.json).

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

## comment 5560080934 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79#issuecomment-5560080934

Created: 2026-09-06T15:01:17Z; updated: 2026-09-06T15:01:17Z

Exact metadata: [source record](sources/comment-5560080934-f8e25faedacf902f99125a7199a7e5ed74d3593511331b6650bb784d3f5bb363.json).

Recovered and continued the interrupted work in #359. Current head: `4f028b6d4addd89b4f9684fdafb5f15dbaa2e6da` (implementation `9d34c9e`), synchronized with master without dropping parallel changes.

The PR now connects enemies, enemy attacks, all 1,024 battle formations, supported-executable shop inventories/global prices, all 18 English kernel2 text sections, and expanded character equipment/materia/AP/growth/limit fields. These have actual UI controls and project save/readback paths, not placeholder tabs. Independent source failures and partial multi-file saves are handled without losing other pending edits.

19 kernel/HTTP and 15 extended binary/safety tests pass locally; seven browser interaction scenarios are included in the FF7 workflow, now running on the synchronized head. Synthetic fixtures/component doubles are not installed-game acceptance.

This issue remains actionable: scene/character AI, field/world placement, growth-curve coefficients and the remaining executable-only character data are not edited, and real installed-edition/deployment/in-game acceptance is still outstanding. Scene block overflow is deliberately refused rather than breaking KERNEL's lookup. Source games are unchanged by binary saves.

Current scope, format references and safeguards are recorded in `codex/ff7-recovery-20260906.md`; that continuation note supersedes the earlier note that scene/shop/kernel2 editors were wholly absent.

## comment 5560080934 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79#issuecomment-5560080934

Created: 2026-09-06T15:01:17Z; updated: 2026-09-06T15:15:01Z

Exact metadata: [source record](sources/comment-5560080934-71f6cfd40932e07c68a8b3d6c75843bbde221340247e6a9b48c4012a9510b6c5.json).

Recovered and continued the interrupted work in #359. Current head: `4f028b6d4addd89b4f9684fdafb5f15dbaa2e6da` (implementation `9d34c9e`), synchronized with master without dropping parallel changes.

The PR now connects enemies, enemy attacks, all 1,024 battle formations, supported-executable shop inventories/global prices, all 18 English kernel2 text sections, and expanded character equipment/materia/AP/growth/limit fields. These have actual UI controls and project save/readback paths, not placeholder tabs. Independent source failures and partial multi-file saves are handled without losing other pending edits.

19 kernel/HTTP and 15 extended binary/safety tests pass locally; seven browser interaction scenarios are included in the FF7 workflow, now running on the synchronized head. Synthetic fixtures/component doubles are not installed-game acceptance.

This issue remains actionable: scene/character AI, field/world placement, growth-curve coefficients and the remaining executable-only character data are not edited, and real installed-edition/deployment/in-game acceptance is still outstanding. Scene block overflow is deliberately refused rather than breaking KERNEL's lookup. Source games are unchanged by binary saves.

Current scope, format references and safeguards are recorded in `codex/ff7-recovery-20260906.md`; that continuation note supersedes the earlier note that scene/shop/kernel2 editors were wholly absent.

## comment 5560080934 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79#issuecomment-5560080934

Created: 2026-09-06T15:01:17Z; updated: 2026-09-06T15:15:01Z

Exact metadata: [source record](sources/comment-5560080934-8339463fb0c85075a5313f3e696d75d1948037633855e3132dbfae81049d3fec.json).

Recovered and continued the interrupted work in #359. Latest continuation head: `eb1e7d3c03a2c1a64d4228fed48f7841a053c488` (main implementation `9d34c9e`), with master's shared Data Map changes preserved.

The PR now connects enemies, enemy attacks, all 1,024 battle formations, supported-executable shop inventories/global prices, all 18 English kernel2 text sections, and expanded character equipment/materia/AP/growth/limit fields. These have actual UI controls and project save/readback paths, not placeholder tabs. Independent source failures and partial multi-file saves are handled without losing other pending edits. It also fixes canonical Data Map navigation and late FFNx coverage updates.

19 kernel/HTTP and 15 extended binary/safety tests pass locally and in CI. All seven FF7 browser interaction scenarios passed on the synchronized implementation; the final integration revision is rerunning them. The real shared Data Map also passed locally for both FF7 editions at three window sizes. Final Windows/Linux shared regressions have passed.

This issue remains actionable: scene/character AI, field/world placement, growth-curve coefficients and the remaining executable-only character data are not edited, and real installed-edition/deployment/in-game acceptance is still outstanding. Scene block overflow is deliberately refused rather than breaking KERNEL's lookup. Source games are unchanged by binary saves.

Current scope, format references and safeguards are recorded in `codex/ff7-recovery-20260906.md`; that continuation note supersedes the earlier note that scene/shop/kernel2 editors were wholly absent.

## comment 5560080934 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79#issuecomment-5560080934

Created: 2026-09-06T15:01:17Z; updated: 2026-09-06T15:17:05Z

Exact metadata: [source record](sources/comment-5560080934-6d83e3515238925de2ffc0e36f0e15301a59080b2818e428c9c3569b082b4574.json).

Recovered and continued the interrupted work in #359. Latest continuation head: `eb1e7d3c03a2c1a64d4228fed48f7841a053c488` (main implementation `9d34c9e`), with master's shared Data Map changes preserved.

The PR now connects enemies, enemy attacks, all 1,024 battle formations, supported-executable shop inventories/global prices, all 18 English kernel2 text sections, and expanded character equipment/materia/AP/growth/limit fields. These have actual UI controls and project save/readback paths, not placeholder tabs. Independent source failures and partial multi-file saves are handled without losing other pending edits. It also fixes canonical Data Map navigation and late FFNx coverage updates.

19 kernel/HTTP and 15 extended binary/safety tests pass locally and in CI. All seven FF7 browser interaction scenarios passed on the synchronized implementation; the final integration revision is rerunning them. The real shared Data Map also passed locally for both FF7 editions at three window sizes. Final Windows/Linux shared regressions have passed.

This issue remains actionable: scene/character AI, field/world placement, growth-curve coefficients and the remaining executable-only character data are not edited, and real installed-edition/deployment/in-game acceptance is still outstanding. Scene block overflow is deliberately refused rather than breaking KERNEL's lookup. Source games are unchanged by binary saves.

Current scope, format references and safeguards are recorded in `codex/ff7-recovery-20260906.md`; that continuation note supersedes the earlier note that scene/shop/kernel2 editors were wholly absent.

## comment 5560080934 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/79#issuecomment-5560080934

Created: 2026-09-06T15:01:17Z; updated: 2026-09-06T15:17:05Z

Exact metadata: [source record](sources/comment-5560080934-d8029510baf0ad156421ed10449a4f34046c47d97a1c591af4ac6896470a25d0.json).

Recovered and continued the interrupted work in #359. Latest continuation head: `eb1e7d3c03a2c1a64d4228fed48f7841a053c488`, with master's shared Data Map changes and parallel game work preserved.

The PR now connects enemies, enemy attacks, all 1,024 battle formations, supported-executable shop inventories/global prices, all 18 English kernel2 text sections, and expanded character equipment/materia/AP/growth/limit fields. These have actual UI controls and project save/readback paths, not placeholder tabs. Independent source failures and partial multi-file saves retain other pending edits. Canonical Data Map navigation and late FFNx coverage updates are fixed.

**Final CI is green:** [FF7 regressions](https://github.com/Lexer-Lux/Lexeditor/actions/runs/34041628509) passed all five jobs, covering 19 kernel/HTTP tests, 15 extended binary/safety tests and seven Chromium interaction scenarios. [Shared checks](https://github.com/Lexer-Lux/Lexeditor/actions/runs/34041628490) passed Windows, Linux and the real shared Data Map browser suite. Both FF7 editions also passed local real-framework layout/navigation checks at three window sizes.

This issue remains actionable: scene/character AI, field/world placement, growth-curve coefficients, inline names and remaining executable-only character initialization are not edited, and real installed-edition/deployment/in-game acceptance is still outstanding. Scene block overflow is deliberately refused rather than breaking KERNEL's lookup. Binary saves leave installed source games unchanged.

Current scope, format references and safeguards are in `codex/ff7-recovery-20260906.md`; that note supersedes the earlier statement that scene/shop/kernel2 editors were wholly absent. The PR is still open and unmerged; this issue is not being closed.
