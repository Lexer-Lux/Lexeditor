# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286202785 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31

Created: 2026-08-29T11:13:00Z; updated: 2026-09-05T06:51:21Z

Exact metadata: [source record](sources/issue-5286202785-221b6dd9e4e8953bfb0dfdddb9ddab39d19af6b9d48f805954bffebd08472423.json).

The plugin needs a structured Formulae primary tab for real game calculations and mod-owned formula changes.

Required behavior:
- Keep Formulae as a normal primary tab in alphabetical order. Tweaks stays last and visually distinct.
- Use structured named terms, bounded controls, formula-specific presets, and live output previews. Do not use unrestricted formula text.
- Show physical damage, physical accuracy, melee damage, magic damage, status infliction, and spell healing with their vanilla and requested reworked formulas.
- Formulae Rework is one mod-owned feature on this page. Full attacker LUCK for physical accuracy and spell-power x MAG healing are parts of it, not separate Tweaks.
- The requested reworked formulas are: melee `(STR + weapon STR bonus) * weapon power`, then a percentage reduction from target VIT; magic `spell power * MAG`, then a percentage reduction from target SPR; status `spell power + MAG - target SPR`, then vanilla status defence; healing `spell power * MAG`.
- Generate only verified FFNx Hext output for the supported FF8 2013 Steam executable. Do not present a preview as an applied game change.
- Keep Flying EVA Bonus in Tweaks as requested. Formulae can show how it affects accuracy, but must not create a second independent value.
- Preserve vanilla and reference comparison and restore behavior for every editable formula term.

Acceptance:
- Formulae contains one Formulae Rework switch. Tweaks contains neither Full LUCK Accuracy nor Spell Healing Rework.
- The unified switch saves with the selected mod and controls every implemented runtime formula patch.
- Saved formula-term changes produce deterministic output and read back.
- FFNx patch-load evidence and in-battle results remain separate runtime acceptance boundaries.

## issue 5286202785 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31

Created: 2026-08-29T11:13:00Z; updated: 2026-09-06T12:45:19Z

Exact metadata: [source record](sources/issue-5286202785-d212d2710da2dd67bce274a84b9f40431a342275892af04ce29e82d0fbc1584e.json).

Provide the requested melee, magic, status, healing and accuracy formulas as one editable, per-mod rework with live previews.

**Incomplete:** healing and accuracy have runtime patches; melee, ordinary magic damage and status infliction do not. The Formulae page also has an unresolved scrolling report. Resolve the remaining rule details and deliver the full feature; a preview is not an applied game change.

## comment 5470755660 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31#issuecomment-5470755660

Created: 2026-08-30T19:23:06Z; updated: 2026-08-30T19:23:06Z

Exact metadata: [source record](sources/comment-5470755660-e84d409e8b38ad313410fca9620dc25960162c648f437ea88517842c40d6a7c2.json).

Formulae now shows the physical-damage and physical-accuracy equations and separates formula text, preview inputs, and editable terms. Flying EVA Bonus is the first real editable term and uses the existing verified patch value. The remaining formula terms are still read-only because their safe executable patch sites are not yet proven, so this issue remains actionable.

## comment 5473626076 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31#issuecomment-5473626076

Created: 2026-08-31T04:15:17Z; updated: 2026-08-31T04:15:17Z

Exact metadata: [source record](sources/comment-5473626076-a15b18d2c09be206d61d7095879563e17286d6421f2504afeae7999f15bc70a5.json).

Formulae now uses the full shared content width. Hidden Edge measured both 1280 and 1600 px layouts with the rightmost card flush to the panel and no horizontal overflow. I also repaired the stale source contract so the preview reads both the enabled state and value from the one shared Flying EVA setting instead of requiring a disabled setting to apply. The issue remains actionable for additional proved formula terms.

## comment 5476616018 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31#issuecomment-5476616018

Created: 2026-08-31T09:46:44Z; updated: 2026-08-31T09:46:44Z

Exact metadata: [source record](sources/comment-5476616018-122ae41ea838fd983585a7cc0ce88de88457a93d086d31a03131b3731d1aa41f.json).

Formulae now edits real stored formula terms instead of only acting as a calculator. Each card has a Weapon Preset selector. Physical Damage edits that weapon's attack power and STR bonus; Physical Accuracy edits its hit rate and melee flag, plus the existing shared Flying EVA setting. The remaining combat-state values stay labeled as preview inputs.

These controls use the same bounds, vanilla/reference values, dirty state, and save route as the Weapons page. A hidden rendered check changed attack power, saw the output update immediately, saved it, reloaded the project, and read the changed value back. Both cards also fit at 1280 and 1600 pixels without overflow.

The implementation is ready for the separate in-game FFNx/battle check.

## comment 5487505078 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31#issuecomment-5487505078

Created: 2026-09-01T01:49:04Z; updated: 2026-09-01T01:49:04Z

Exact metadata: [source record](sources/comment-5487505078-e976bfbcce5b8ec2db6769b1accbc78dfb300376fa84152d5ba2f84da708182e.json).

Repaired the curve formula rendering. Long equations now compress whole glyphs instead of collapsing only letter spacing, and the displayed character/enemy equations use shorter equivalent notation. Rendered bounds checks keep every formula inside its graph; STR, VIT, and MAG no longer pile glyphs on the curve.

## comment 5539023282 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31#issuecomment-5539023282

Created: 2026-09-04T10:16:20Z; updated: 2026-09-04T10:16:20Z

Exact metadata: [source record](sources/comment-5539023282-3bf449d53936908f5a605da4a80cf30a1053b599ce40cd9590f2919ece5942cc.json).

The Formulae view does not scroll, so most formula content is unreachable. Make its content area scroll within the available panel height.

## comment 5543550340 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31#issuecomment-5543550340

Created: 2026-09-04T16:32:59Z; updated: 2026-09-04T16:32:59Z

Exact metadata: [source record](sources/comment-5543550340-77e1b2ec80de997314439750efa83acf3c0b13f0caab3a8e32a7c77af3e8cfa4.json).

Runtime audit result: spell healing (spell power × attacker MAG) and full attacker LUCK in physical accuracy have complete executable patches and mutation contracts. The master Formulae Rework remains unavailable because melee damage, ordinary magic damage, and status infliction are still presentation-only. Their current descriptions do not define the VIT/SPR percentage denominator and >100 behavior, random and clamp preservation, attack-type scope, or how status accuracy values 250–255 and existing special cases should interact with the new chance. I did not invent those rules. Please define those remaining details; then the three runtime patches can be completed as one Formulae Rework.

## comment 5550092432 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/31#issuecomment-5550092432

Created: 2026-09-05T06:51:21Z; updated: 2026-09-05T06:51:21Z

Exact metadata: [source record](sources/comment-5550092432-5c37f27f6b2379b0168474ec42740769f9806b88b9bf50c94d6d43a4b2ebb0ab.json).

Lexer reports that the expected complete formula-replacement tweak is still missing after extensive work. The old handoff describes only full-LUCK accuracy and spell healing as coded; the master feature remains unavailable because the melee, magic-damage, and status rules remain unresolved. This is incomplete implementation, not a working delivered tweak. Resolve the existing design decisions without inventing new gameplay rules, then deliver and validate the complete feature. Deferred; no code work resumed.
