# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356301152 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/176

Created: 2026-08-06T03:28:28Z; updated: 2026-09-05T06:58:52Z

Exact metadata: [source record](sources/issue-5356301152-1a16ffb694514e78dd34a295df61ac4dc76644f4e3a6f4cdc48c34233ef1fe6c.json).

STATUS: Fixed, built, and queued for automatic installation when RDR2 exits. Needs in-game confirmation after a full restart.

## Problem
When the outer Dead Eye bar is exhausted, Dead Eye lingers briefly and stops, but it can immediately be activated again with no bar. The reactivated state can then persist indefinitely.

## Required behavior
- Dead Eye must end immediately when its outer bar reaches empty.
- Dead Eye must remain unavailable while the outer bar is empty.
- It may become available again only after the outer bar has genuinely refilled above the empty boundary.
- The Dead Eye core must not act as a reserve bar.

## Implemented
- Uses Rockstar's normalized Dead Eye meter rather than inferring emptiness from raw points and a learned maximum.
- Latches the exhausted state and ends/blocks Dead Eye every frame while empty.
- The latch can clear only while Dead Eye is inactive and the meter has genuinely refilled above the cutoff.
- A slipped Dead Eye-core reserve tick raises the same latch and is restored.

## In-game test
1. Fully restart the game after the queued installer runs.
2. Exhaust the outer Dead Eye bar while Dead Eye is active and confirm it ends immediately.
3. Attempt to reactivate Dead Eye while the bar remains empty and confirm activation is rejected/ended.
4. Refill the outer bar, confirm Dead Eye becomes usable again, and confirm the core was not consumed.

## issue 5356301152 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/176

Created: 2026-08-06T03:28:28Z; updated: 2026-09-06T12:54:58Z

Exact metadata: [source record](sources/issue-5356301152-c085fcc12a34a5507b8fcb04ea526fc54ed48f04b3b8153733acd76b9b990bb2.json).

Empty outer bars must not use cores as reserve fuel. Dead Eye must stop and stay unavailable while empty; Eagle Eye must still work. Exhausted horses must slow enough to regenerate automatically.

**Status: Partly repaired.** The Eagle Eye correction is installed, but the reported horse recovery problem is not resolved in the later notes. Finish that missing behavior before overall acceptance.

## comment 5550129472 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/176#issuecomment-5550129472

Created: 2026-08-06T07:32:56Z; updated: 2026-08-06T07:32:56Z

Exact metadata: [source record](sources/comment-5550129472-ad6c86706c0b7fff6798ac993de26b3a33caf374c6422b3bbf68e43f5049ad61.json).

This fix was included in the release build installed and hash-verified at 2026-08-06 01:18 MDT, so the stale `actionable` label was wrong. Moved to `test me` for the restart/exhaust/reactivation/refill checks already listed in the issue.

Installed ASI SHA-256: `85C62841F5F6C8C5B2D069A0965D3AAFA703095B9B0B74876E7728BFE5ED5D32`

## comment 5550129492 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/176#issuecomment-5550129492

Created: 2026-08-06T11:26:09Z; updated: 2026-08-06T11:26:09Z

Exact metadata: [source record](sources/comment-5550129492-c1d466aaefd69982549d40e96e740e32cbc33ea79a9c920c7770eb6987c5d413.json).

now i can just use deadeye forever. my bar drains, hits 0, and i'm still in deadeye.

## comment 5550129500 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/176#issuecomment-5550129500

Created: 2026-08-06T12:58:35Z; updated: 2026-08-06T12:58:35Z

Exact metadata: [source record](sources/comment-5550129500-6c4ffc93fcf9fd50e14e3e6f2bccb83a68f7698957ce3d935c689cc81bc6ae21.json).

nothing has been changed.

## comment 5550129513 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/176#issuecomment-5550129513

Created: 2026-08-06T14:42:13Z; updated: 2026-08-06T14:42:13Z

Exact metadata: [source record](sources/comment-5550129513-b1ce00eeea0935a5045184177a533163e576763578ea7a3396bf66b602cd07d2.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Empty the Dead Eye outer bar and confirm Dead Eye deactivates, remains blocked while empty, and returns after refilling above the threshold.

## comment 5550129522 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/176#issuecomment-5550129522

Created: 2026-08-06T18:54:09Z; updated: 2026-08-06T18:54:09Z

Exact metadata: [source record](sources/comment-5550129522-120bc7af7d472f0ce33b754f648fd374f07bc456458b1f391d31b68bee1baf6a.json).

some weirdness...if i run out of horse stamina, it won't run into its core. good. but, it never starts regenerating again unless i intentionally slow it with ctrl. compare this to on foot, where you immediately leave your running mode so you can start regenerating stamina. it should work the same way on the horse.

## comment 5550129537 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/176#issuecomment-5550129537

Created: 2026-08-09T09:42:35Z; updated: 2026-08-09T09:42:35Z

Exact metadata: [source record](sources/comment-5550129537-f015d944cbab2765af9e0b0911603d17d39b0fd2fc6586fc58ff49c2f6c529ba.json).

Installed repair for the MMB/Eagle Eye regression. The empty-Dead-Eye latch was suppressing the shared special-ability controls every frame, including MMB's non-aiming Eagle Eye context. Those control suppressions are removed; Dead Eye remains blocked only through the Dead Eye-specific native. Installed/source/manifest SHA-256: F1852A53EA48C933C9E12420E3CC8589C34E3D8FA4FCA0D31EE63B28DC89BF28. Test ordinary MMB Eagle Eye, exhaust Dead Eye, verify empty-ring Dead Eye remains blocked, then verify MMB Eagle Eye still works.
