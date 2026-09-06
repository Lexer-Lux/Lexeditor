# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5364855604 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/357

Created: 2026-09-06T12:09:57Z; updated: 2026-09-06T12:23:10Z

Exact metadata: [source record](sources/issue-5364855604-fc4ec1aa03efa88ffa85d5151ae0a68d433c4b4b5eaff14d849274130d20df12.json).

Using binoculars crashed the game as they reached the player's face, before the binocular view opened.

**Status: Needs investigation.** One occurrence reported; the cause and repeatability are unknown. No fix is ready to test.

Related binocular work: #104, #181, #158 and #235.

## issue 5364855604 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/357

Created: 2026-09-06T12:09:57Z; updated: 2026-09-06T13:32:22Z

Exact metadata: [source record](sources/issue-5364855604-a220e76a5221e073358f08caa3de33f2d43d27e3c3ff34021ad7431ca293a244.json).

**Actionable — needs investigation.** Using binoculars crashed the game as they reached the player’s face, before binocular view opened. One occurrence is reported; repeatability and cause are unknown.

No fix is ready to test. Related binocular work: #104, #181, #158 and #235.

## issue 5364855604 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/357

Created: 2026-09-06T12:09:57Z; updated: 2026-09-06T13:32:22Z

Exact metadata: [source record](sources/issue-5364855604-c11d0c735afb3f26dd08d9e0a56a83ccb9981c5b7e2998ab441194917b7d6ef9.json).

**Actionable — needs investigation.** Using binoculars crashed the game as they reached the player’s face, before binocular view opened. One occurrence is reported; repeatability and cause are unknown.

No fix is ready to test. Related binocular work: #104, #181, #158 and #235.

## issue 5364855604 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/357

Created: 2026-09-06T12:09:57Z; updated: 2026-09-06T15:01:11Z

Exact metadata: [source record](sources/issue-5364855604-00b0808a315b88b3973ce12d742c92a3d11ac5abf4a13e722bd4ca81379dd799.json).

**Actionable — needs investigation.** Using binoculars crashed the game as they reached the player’s face, before binocular view opened. One occurrence is reported; repeatability and cause are unknown.

No fix is ready to test. Related binocular work: #104, #181, #158 and #235.

## comment 5560080389 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/357#issuecomment-5560080389

Created: 2026-09-06T15:01:11Z; updated: 2026-09-06T15:01:11Z

Exact metadata: [source record](sources/comment-5560080389-0a511ef6cdc250f631807d6c5f57a87ea43e8d0ae4eb09a7681047572aa34c55.json).

Partial safety/diagnostic source candidate: Lexer-Lux/Lexers-Mod-For-RDR2#211. This is NOT a claim that the reported binocular crash is fixed.

Found a demonstrable null-dereference hazard in the native put-away prompt scan: three getGlobalPtr results were read without checking them. The candidate guards each result while preserving the existing registry bounds/identifiers and unrelated prompts. Added granular crash-stage markers around binocular task status, readiness, prompt scanning, forced aim and the update dispatch, without deleting existing evidence or changing trace rotation.

The actual production prompt routine was extracted, compiled as C++17 with -Wall -Wextra -Werror, and executed against synthetic missing-pointer, invalid-handle, wrong-action, exact-match and registry-boundary cases. Those tests and the runtime PR's source CI pass.

No production ASI build/install, game crash reproduction, or proof that this hazard caused #357. Remaining work: build using the repository's prescribed SDK/toolchain, reproduce against the candidate, and inspect preserved crash-stage evidence. Keep the issue open/actionable; #364 contains the central handoff, not a runtime binary.
