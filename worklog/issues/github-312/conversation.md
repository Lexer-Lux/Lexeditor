# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356483893 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/312

Created: 2026-08-29T15:23:54Z; updated: 2026-09-05T14:09:41Z

Exact metadata: [source record](sources/issue-5356483893-003b23f2b0d76f88df18e7e4dac1f7ddd39dc4a4c137267f112c8ca152dcf120.json).

Use four commands: Attack, Magic, the character command, then the command from the character’s single junctioned GF. Require Single GF mode.

Character commands: Rinoa—Angelo (not yet defined), Quistis—Draw, Squall—Switch, Zell—Defend, Selphie—Summon, Irvine—Shoot. GF commands keep their requested mapping, including Tonberry’s Lv Down/Lv Up alternate.

Corrected the learned-ability check: junctioning Siren alone must not grant Treatment. Remaining custom command behavior is tracked in #314.

Check the repair:
- [ ] Restart Lexeditor, enable Single GF and Command Menu Rework, save, and enter battle with Siren junctioned before she learns Treatment. Confirm Treatment cannot be used.
- [ ] With Treatment learned, confirm it becomes usable. Remove Siren and confirm it is no longer supplied. Report any wrong command or availability.


## issue 5356483893 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/312

Created: 2026-08-29T15:23:54Z; updated: 2026-09-06T12:59:33Z

Exact metadata: [source record](sources/issue-5356483893-f80093a34ba81fadd73fdf6276248fe0a35ecae9f0115e0a70a6b32f413a609f.json).

Use Attack, Magic, the character command and the learned command from the single junctioned GF. Removing a GF must remove its command.

**Status: Partly repaired.** The Siren/Treatment learning gate is corrected in the latest handoff, but custom commands in #314 and undefined Angelo behavior remain open. Do not label the complete command rework finished from the Treatment repair alone.

## comment 5550344706 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/312#issuecomment-5550344706

Created: 2026-08-29T22:07:29Z; updated: 2026-08-29T22:07:29Z

Exact metadata: [source record](sources/comment-5550344706-2e6a9fb2d64afb37ab13af105979a54985296a4dc2a287bc12e4782cf3d86b55.json).

The verified descriptor builder now maps Magic, the supported character commands, and every requested GF command from the installed kernel. Rinoa's undefined Angelo slot stays explicitly unavailable. The full Fixed Command Menu control remains hidden until Switch, GF Magic pages, and the complete live GF-derived refresh path are safe; the implemented Irvine Shoot slice is exposed under its own accurate toggle instead.

## comment 5550344715 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/312#issuecomment-5550344715

Created: 2026-08-29T22:14:21Z; updated: 2026-08-29T22:14:21Z

Exact metadata: [source record](sources/comment-5550344715-8f9803a2c5865d914bf37c0bd30a4d19f37b77ef338826c1375bbdb4a599ce1a.json).

The guarded four-slot descriptor builder is now implemented: vanilla Attack, Magic, the supported character command, and the one-hot Single GF command. It covers every character and all 16 GF masks without invented substitutions; zero or legacy multi-GF masks leave the GF slot empty. The global toggle remains hidden because Switch and GF Magic pages are not complete.

## comment 5550344727 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/312#issuecomment-5550344727

Created: 2026-08-30T20:30:53Z; updated: 2026-08-30T20:30:53Z

Exact metadata: [source record](sources/comment-5550344727-27fa8fd39a48b53d4e9017f41850f2cf18433f7786b48b54f595b06ddb7e3055.json).

The fixed command builder now emits the complete supported composition under Monogamy: Attack, Magic, the character command, and the learned GF command. Tonberry uses FF8's existing alternate flag and hidden descriptor for LV Up. Rinoa's third slot stays blank because Angelo remains TBD. Static composition checks pass; the command dispatch still needs an in-game check.

## comment 5550344745 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/312#issuecomment-5550344745

Created: 2026-08-31T05:27:05Z; updated: 2026-08-31T05:27:05Z

Exact metadata: [source record](sources/comment-5550344745-92d0fc30cbffecaab0d7bd73355e48bce91049916e53d4917621de2b186a08c8.json).

Switch was entering FF8's normal target builder with a target byte that the patch and verifier had wrongly called self/no-target. Both crash attempts failed at the same target-bounds dereference because that path produced no valid target.

I moved Switch to the confirmed-command boundary before target construction. It now treats Squall as implicit, opens the GF selector directly, and never asks for a target. The old late state-12 hook and `0x18` target form are now rejected by the verifier. I regenerated the active Hext patch. Please restart FF8, select Switch, and check open, cancel, and confirm; the issue stays waiting for that in-game result.

## comment 5550344753 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/312#issuecomment-5550344753

Created: 2026-09-05T06:34:12Z; updated: 2026-09-05T06:34:12Z

Exact metadata: [source record](sources/comment-5550344753-598da78e3ded266826f14c1b7c153d2588cc3b287a579769a47d3cb60c00d659.json).

Remaining acceptance from the retired handoff: Quistis reportedly retains Treatment after the GF is removed. Confirm that unjunctioning removes the GF-specific command and keeps Quistis’s fixed Draw command. The recorded validator/availability-bitset investigation is preserved in the local issue worklog; no further debugging is being started. This remains part of the existing command-menu issue.

## comment 5550344764 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/312#issuecomment-5550344764

Created: 2026-09-05T06:51:12Z; updated: 2026-09-05T06:51:12Z

Exact metadata: [source record](sources/comment-5550344764-2dc17f36ad8320e02c3119a9b7baeae3ace6abd9eb3d7618f4ae6207d59f65ea.json).

New learning-gate failure: Quistis can use Treatment even though her junctioned Siren has not learned Treatment. This differs from the earlier unjunctioning report. Junctioning a GF alone must not bypass the required learned ability. Check both unlearned/learned states and removal of the GF, while preserving the fixed character command. Deferred; current behavior is not accepted.
