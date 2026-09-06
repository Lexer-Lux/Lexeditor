# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356301550 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/178

Created: 2026-08-06T03:38:20Z; updated: 2026-09-05T06:58:58Z

Exact metadata: [source record](sources/issue-5356301550-03f39fa4f221a6c41b195c16e6fe3706377b40d91c9ea55ee86ec75d888c6382.json).

## Goal

For each of these, I need to make sure they:
- Appear at the right time
- Show up in the right place
- Disappear at the right time

## Test checklist

- [ ] **Cigarette Cards (144):** after the cigarette-card quest begins, check several still-uncollected cards in widely separated regions—especially New Austin/West Elizabeth and Lemoyne—and confirm every marker lands on the physical card. All 144 coordinates were replaced with game-space placements and are installed. World Champions cards 2 and 11 intentionally share one shack windowsill.
- [ ] **Dinosaur Bones (30):** markers remain hidden until the bone hunt has begun, then point to the physical bones.
- [ ] **Rock Carvings (10):** markers use the game's own placement coordinates, do not duplicate the CSV markers, and disappear when the game reports the carving found.
- [ ] **Dreamcatchers (20):** all twenty markers occupy distinct locations rather than collapsing onto one point, and each lands on its dreamcatcher.
- [ ] **Graves (8):** each grave appears only after that character's death mission, never spoils a living character, and points to the correct grave. Detailed gate testing is also tracked in #41.
- [ ] **Exotics (235 locations):** only the currently unlocked request-stage items appear; repeated flower/plume names retain separate markers and do not collapse or retire as a group.
- [ ] **Legendary Fish (14):** markers remain hidden until the legendary-fish quest begins and identify the correct fishing area rather than pretending the fish is a fixed pickup.
- [ ] **Shacks (40):** all are immediately available and each marker points to the correct shack/homestead.
- [ ] **Treasure-map clues and pickups (20):** each marker points to a map or clue pickup. Actual treasure caches remain deliberately unmarked so the treasure maps still have a purpose.
- [ ] **Points of Interest (57):** each marker points to the correct inspect/journal location.

## Shared behavior to test

- [ ] The ten categories appear as ten grouped entries in the map Index instead of hundreds of individual names.
- [ ] Cycling a grouped Index entry moves between that category's markers.
- [ ] Each category's INI toggle hides and restores only that category.
- [ ] Custom card, bone, carving, dreamcatcher, and treasure-map artwork loads correctly instead of rendering as black squares. Artwork revisions remain tracked in Lexer-Lux/Lexeditor#138.
- [ ] Story/quest gates update without requiring a new save.
- [ ] If a marker is inaccurate, standing at the correct location and pressing **F2** relocates only the nearest individual marker and the correction survives restart.

## Status

Built and installed; needs in-game confirmation. The corrected cigarette-card CSV in the game folder exactly matches the project copy.

Known scope exclusions: actual treasure caches are intentionally hidden. Legendary-animal territories and fixed gang hideouts are not part of this installed ten-category pass.

## issue 5356301550 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/178

Created: 2026-08-06T03:38:20Z; updated: 2026-09-06T12:55:03Z

Exact metadata: [source record](sources/issue-5356301550-1b208f854ab20dcc85a066089ea2d926bae6eaef1f2c2fe8bf72b5a106cc60b7.json).

Ten marker categories are installed: cards, bones, carvings, dreamcatchers, graves, exotics, legendary fish, shacks, treasure clues and points of interest. Actual treasure caches stay unmarked.

**Status: Overall acceptance remains incomplete.** Location auditing continues in #274. Prepare representative before/after quest saves and expected markers for the gate checks. POIs must disappear after their journal sketch, not merely on approach.

## comment 5550129878 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/178#issuecomment-5550129878

Created: 2026-08-06T05:15:28Z; updated: 2026-08-06T05:15:28Z

Exact metadata: [source record](sources/comment-5550129878-66f1de5ab629fe38cfa18d068c1ecea3a5d054bce9c42f7f2900ce34bd59729f.json).

what happened to the gang hideouts?

## comment 5550129893 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/178#issuecomment-5550129893

Created: 2026-08-06T09:12:47Z; updated: 2026-08-06T09:12:47Z

Exact metadata: [source record](sources/comment-5550129893-2d74ad09cdfe51f5a423b308c186065ca5331bce38efbd4c49e02e6151158611.json).

what happened to the gang hideouts?

## comment 5550129898 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/178#issuecomment-5550129898

Created: 2026-08-06T10:54:33Z; updated: 2026-08-06T10:54:33Z

Exact metadata: [source record](sources/comment-5550129898-123e4395be23ce25df875058b3b1b5cddeca9769beb0adf9fc139aa23ba70bb6.json).

what happened to the gang hideouts and points of interest?

## comment 5550129913 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/178#issuecomment-5550129913

Created: 2026-08-06T11:12:52Z; updated: 2026-08-06T11:12:52Z

Exact metadata: [source record](sources/comment-5550129913-7391878ecccf31846e74265549cf5f89a2412fcd59331718e7a4922f7d668e30.json).

what happened to the gang hideouts and points of interest?

## comment 5550129926 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/178#issuecomment-5550129926

Created: 2026-08-06T13:39:52Z; updated: 2026-08-06T13:39:52Z

Exact metadata: [source record](sources/comment-5550129926-422699c3eca6f4686fc0ea1309fdc6a336269ef194e680f1f97ac3df950b3a74.json).

You said something was wrong with POIs though? Can you fix them, then? Or did you already?

## comment 5550129936 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/178#issuecomment-5550129936

Created: 2026-08-06T14:42:16Z; updated: 2026-08-06T14:42:16Z

Exact metadata: [source record](sources/comment-5550129936-ca5284e495092b505fef467603876972bdac71127497db923b04d27038b32272.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Test an uninspected POI remains after entering its radius, disappears only after its journal sketch completes, already-discovered POIs stay absent, and Jesuit Missionary/Sperm Whale markers land correctly.
