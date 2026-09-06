# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356292759 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/137

Created: 2026-08-06T02:14:20Z; updated: 2026-09-05T06:56:52Z

Exact metadata: [source record](sources/issue-5356292759-567bc608da0f37aca025bd4d0cadd2ec21cb6e820241107c8b7452680ef71f85.json).

PREMIUM-CIGARETTE CARD DROPS — simply acquiring a Premium Cigarette pack should stop
     granting a card. Instead, each premium pack SMOKED has a 20% chance to grant a
     random card I don't own; once all 144 are owned, duplicates are allowed.
     Loose world cards stay normally collectible and existing cards are kept.
     Wait, doesn't the pack itself just give you the separate cigarettes item? I
     want to locate them, make sure they're separately and properly labelled in
     the editor, then make consuming the actual cigarette the thing that procs
     it. ~Lex
     Built and staged; needs a test pass on buy / collect / discard / smoke
     many, plus stranger-mission and set turn-in recognition.

## issue 5356292759 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/137

Created: 2026-08-06T02:14:20Z; updated: 2026-09-06T12:47:11Z

Exact metadata: [source record](sources/issue-5356292759-93291f7a2082b8c238730f1b7c409e4cd6aaccbd9027a6346cdd0fea1407215c.json).

Acquiring or discarding cigarettes must not grant a card. Smoking the actual premium cigarette should roll the configured chance, default 20%, preferring unowned cards until all 144 are owned. Existing cards and loose world pickups remain intact.

**Status: The corrected smoking-trigger implementation is not verified installed.** Deliver it and prepare deterministic 0%/100% tests before another player check.

## comment 5550119694 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/137#issuecomment-5550119694

Created: 2026-08-10T09:44:41Z; updated: 2026-08-10T09:44:41Z

Exact metadata: [source record](sources/comment-5550119694-97426452b0950e6266b39f2d3dea248b0e8cf4c5eb2d4bfd4d72fddafd5c1f72.json).

Let me configure the % chance in settings. I have no idea if this is broken or I'm just unlucky.

## comment 5550119710 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/137#issuecomment-5550119710

Created: 2026-08-10T10:08:16Z; updated: 2026-08-10T10:08:16Z

Exact metadata: [source record](sources/comment-5550119710-d5874955b29ed544fce861bb464c0c2a5d83f42277c48fc786e97da51e0b400d.json).

Source implementation is complete and integrated for the next combined build. The card roll now uses Rockstar's authored smoking consume event instead of inferring a smoke from inventory-count changes. `[PremiumCigaretteCards] ChancePercent` is editable from 0-100 and hot-reloads within about two seconds; buying, collecting, or discarding a pack does not roll. Successful smokes select an unowned card first, then allow duplicates after all 144, with inventory readbacks and an idle heartbeat so a miss can be distinguished from non-execution.

This remains actionable until the combined ASI is installed and hash-verified. Runtime still needs the requested 0%/100%, buy/collect/discard/smoke, loose-card, all-144, stranger-mission, and set-turn-in tests.
