# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356296441 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153

Created: 2026-08-06T02:37:47Z; updated: 2026-09-05T06:57:45Z

Exact metadata: [source record](sources/issue-5356296441-1b2b989b6fd39208bc75ece4b3cac327f7657e42dcfc3a25f50fbb452410c036.json).

(No body was present in this captured version.)

## issue 5356296441 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153

Created: 2026-08-06T02:37:47Z; updated: 2026-09-06T12:54:19Z

Exact metadata: [source record](sources/issue-5356296441-53cb2b4815570b6de7f7ea0f79c234c735b8dcd750c19bedd6b0baecd7219404.json).

After the final swig and stowing animation, grant one empty bottle and show its real acquisition notification.

**Status: Source cleanup is complete, but not built or installed.** The obsolete Force Acquisition Feed setting was removed from all settings surfaces. Deliver that candidate before another bottle test.

## issue 5356296441 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153

Created: 2026-08-06T02:37:47Z; updated: 2026-09-06T13:54:51Z

Exact metadata: [source record](sources/issue-5356296441-9764f85eb674a32d0bedc2ae28070c8871c5b486d76022b53324dfc8f5b79bb4.json).

After the final swig and stowing animation, grant one empty bottle and show its real acquisition notification.

**Status: Source cleanup is complete, but not built or installed.** The obsolete Force Acquisition Feed setting was removed from all settings surfaces. Deliver that candidate before another bottle test.

## issue 5356296441 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153

Created: 2026-08-06T02:37:47Z; updated: 2026-09-06T17:14:33Z

Exact metadata: [source record](sources/issue-5356296441-6635ce3d08fc8914e7375bc902bc01f08e578aa0efdd6d4ebcbb4c71c5ccddae.json).

After the final swig and stowing animation, grant one empty bottle and show its real acquisition notification.

**Status: Source cleanup is complete, but not built or installed.** The obsolete Force Acquisition Feed setting was removed from all settings surfaces. Deliver that candidate before another bottle test.

## comment 5550124046 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153#issuecomment-5550124046

Created: 2026-08-06T06:42:29Z; updated: 2026-08-06T06:42:29Z

Exact metadata: [source record](sources/comment-5550124046-51f51f6c43da4c25c1772c8edae83654f698dfa9ffe6cc8ffd9c581927cba52a.json).

I CAN'T EVEN AFFORD BOOZE TO TEST THIS BECAUSE OF Lexer-Lux/Lexeditor#208 

## comment 5550124061 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153#issuecomment-5550124061

Created: 2026-08-20T12:02:36Z; updated: 2026-08-20T12:02:36Z

Exact metadata: [source record](sources/comment-5550124061-fe56b994c59b297898a54ef08d986f7621150cf44fbddbc27cdfeac79a720a75.json).

The optional empty-bottle fallback was another centre-screen fake notification. It was disabled by default, but it is now deleted completely. Confirmed bottle grants retain the existing Rockstar acquisition feed after inventory readback, so the fallback cannot duplicate or replace it.

Test one supported final swig: the empty-bottle count must increase and one normal Rockstar acquisition notification must appear.

## comment 5550124070 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153#issuecomment-5550124070

Created: 2026-08-20T14:18:45Z; updated: 2026-08-20T14:18:45Z

Exact metadata: [source record](sources/comment-5550124070-eca3df4fc88469a38cdba7323bba36187759a427020068ec389b47df2a94cbae.json).

The runtime bottle path is correct, but the old Force Acquisition Feed setting was not fully deleted: it still appears in the main INI, the generated settings menu, the LEXEDITOR schema, and the Lexer-Lux/Lexeditor#117 settings contract. The Lexer-Lux/Lexeditor#153 contract now catches that recurrence and intentionally stays red until those shared entries are removed together. The bottle module itself still uses the final-swig, stow, inventory-count readback, and real Rockstar acquisition-feed sequence. No build or install was performed.

## comment 5550124086 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153#issuecomment-5550124086

Created: 2026-08-20T14:26:22Z; updated: 2026-08-20T14:26:22Z

Exact metadata: [source record](sources/comment-5550124086-c533e4c9f9a9dadf74547eac1ab8150be3ed6413248dd35bf33f25cfef1598f2.json).

Shared settings cleanup is now complete. Force Acquisition Feed is gone from the main INI, LEXEDITOR schema, generated in-game menu, and Lexer-Lux/Lexeditor#117 lifecycle contract. The full Lexer-Lux/Lexeditor#153 contract now passes and rejects the fake notification path while preserving the real final-swig, stow, inventory-count readback, and Rockstar acquisition feed. This is not built or installed, so Lexer-Lux/Lexeditor#153 remains actionable.

## comment 5560838561 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/153#issuecomment-5560838561

Created: 2026-09-06T17:14:33Z; updated: 2026-09-06T17:14:33Z

Exact metadata: [source record](sources/comment-5560838561-8746ef9a254889f82be61364df678dbdf0fc87555d5e031cc97753b6801838af.json).

Found the issue status was stale: the synthetic ForceAcquisitionFeed fallback still existed in current runtime source/settings. It is now fully removed—implementation, config reader/state, entire INI block, schema metadata and generated menu row. Settings lifecycle/menu checks caught and prevented two stale-cleanup mistakes before the final commit. Current release/development builds pass in runtime PR #211. Broader collectible-bottle/real-feed gameplay behavior remains unconfirmed, so this issue stays actionable.
