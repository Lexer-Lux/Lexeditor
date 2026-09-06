# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356311042 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/215

Created: 2026-08-06T10:01:10Z; updated: 2026-09-05T07:00:59Z

Exact metadata: [source record](sources/issue-5356311042-88185f781a9c0cb0f70375bf298ff349002175d12dbc56d58d99e2b271b80c7b.json).

## Problem\n\nAfter every death and respawn, the camera spends roughly ten seconds flying left/right/up/down across large distances before settling back on the player. This began with the authored-campsite respawn system.\n\n## Required behavior\n\n- Respawning must not repeatedly drag the gameplay camera across the world.\n- Campsite respawn may move the player once to a safe point beside the nearest activated campsite, but must not teleport the ped every frame while collision/control settles.\n- If a safe campsite destination is unavailable, leave the player at Rockstar's normal respawn rather than producing camera flight.\n\n## In-game acceptance\n\n1. Die and respawn with an activated campsite far from the death/vanilla-respawn area.\n2. Confirm the transition completes cleanly without multi-second camera travel or oscillation.\n3. Confirm Arthur finishes beside—not inside—the activated campfire.\n4. Repeat without an activated campsite and confirm vanilla respawn/camera behavior remains unchanged.

## issue 5356311042 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/215

Created: 2026-08-06T10:01:10Z; updated: 2026-09-06T13:17:42Z

Exact metadata: [source record](sources/issue-5356311042-72a1ae30a07960a2f0a70094cdf1d85b31203682e76f18fd500ea668996783de.json).

**Status: Closed historical repair.** Repeated per-frame player relocation was replaced with one validated move after normal respawn. This issue’s last delivery note was still queued; current campsite selection and placement work remains in #244 and #172.

## comment 5550140090 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/215#issuecomment-5550140090

Created: 2026-08-06T10:03:55Z; updated: 2026-08-06T10:03:55Z

Exact metadata: [source record](sources/comment-5550140090-3b60a7d414e36d8a12bdf39be6f5a4e022b6dd19583bf37c0109dfa542524d09.json).

Confirmed root cause and implemented the fix. The campsite respawn loop called \SET_COORDS_HEADING\ on Arthur every frame for up to the 15-second settle window, making the gameplay camera chase repeated world-space corrections. It now waits for Rockstar's completed respawn latch, instant-fades, moves Arthur exactly once to the validated point beside the campfire, waits for collision without moving again, and fades back in over 300 ms. If no safe point resolves, it leaves the vanilla respawn untouched. Static one-shot verification and the full release build passed. The current release hash is \F993C94789978F75AC93DCC762890B2136068700EFD85FABA8A0749FF358D6F4\; installation is queued for when the currently running RDR2 process closes, so the issue remains \ctionable\ until hash-verified installation lands.

## comment 5550140090 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/215#issuecomment-5550140090

Created: 2026-08-06T10:03:55Z; updated: 2026-08-06T10:03:55Z

Exact metadata: [source record](sources/comment-5550140090-64b54f34c6d6bc8abdb75079b0ecac55df8a77affd6919eb30cd693df43c7d4c.json).

Confirmed root cause and implemented the fix. The campsite respawn loop called \SET_COORDS_HEADING\ on Arthur every frame for up to the 15-second settle window, making the gameplay camera chase repeated world-space corrections. It now waits for Rockstar's completed respawn latch, instant-fades, moves Arthur exactly once to the validated point beside the campfire, waits for collision without moving again, and fades back in over 300 ms. If no safe point resolves, it leaves the vanilla respawn untouched. Static one-shot verification and the full release build passed. The current release hash is \F993C94789978F75AC93DCC762890B2136068700EFD85FABA8A0749FF358D6F4\; installation is queued for when the currently running RDR2 process closes, so the issue remains \^Gctionable\ until hash-verified installation lands.
