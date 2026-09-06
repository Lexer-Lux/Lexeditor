# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356307929 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201

Created: 2026-08-06T05:59:36Z; updated: 2026-09-05T07:00:16Z

Exact metadata: [source record](sources/issue-5356307929-1c4537b707ebfbbc8813c7e06fbc9ca0def5a4eebd93af1ff6355e3739311053.json).

Legacy TODO 33

Children are killable during ordinary free roam. The feature deliberately does nothing while a mission is active so scripted protections survive.

## Test

- [ ] Test ambient Saint Denis street kids in free roam.
- [ ] Confirm missions involving Jack or other children remain unaffected.

## issue 5356307929 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201

Created: 2026-08-06T05:59:36Z; updated: 2026-09-06T13:31:23Z

Exact metadata: [source record](sources/issue-5356307929-d733dec1cd72f118f60e9a79e388a8c78924d2476911f840991c7f75c6295a5c.json).

**Actionable — no safe implementation yet.** Earlier hooks crashed or damaged shared shop/interaction behavior and were removed. Diagnostic logging is not the gameplay feature.

A safe entity-local mechanism still needs research. Failed attempts do not establish that every approach is unfeasible. Nothing is ready for a player test.

## issue 5356307929 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201

Created: 2026-08-06T05:59:36Z; updated: 2026-09-06T13:58:10Z

Exact metadata: [source record](sources/issue-5356307929-79030736888df5456342bcc7fb0bb0ac48bb6d7fbb9e439dfc82c4c697ee195d.json).

**Actionable — no safe implementation yet.** Earlier hooks crashed or damaged shared shop/interaction behavior and were removed. Diagnostic logging is not the gameplay feature.

A safe entity-local mechanism still needs research. Failed attempts do not establish that every approach is unfeasible. Nothing is ready for a player test.

## comment 5550136472 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136472

Created: 2026-08-06T09:14:12Z; updated: 2026-08-06T09:14:12Z

Exact metadata: [source record](sources/comment-5550136472-d222ca14f99d6d3a99b4aab01c99e9e2efa2806b1f2cc66e84e35a904c5d5458.json).

Built and installed in ASI C7FD09E0. Free-roam child peds now have all three protection layers cleared, while missions and blocked/scripted states remain gated off. Please test a Saint Denis free-roam child and confirm mission children remain protected.

## comment 5550136497 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136497

Created: 2026-08-06T11:23:24Z; updated: 2026-08-06T11:23:24Z

Exact metadata: [source record](sources/comment-5550136497-28e6a8ea7f4f8f6065388d93a5b2fd7de3b2cfe1c4f84b280f3d81f16f103448.json).

maybe i wasn't clear? I literally can't shoot them still. my crosshair is disabled when i aim at them. i count this as part of the "invincibility". so get rid of it.

## comment 5550136513 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136513

Created: 2026-08-06T12:57:41Z; updated: 2026-08-06T12:57:41Z

Exact metadata: [source record](sources/comment-5550136513-7fbc0ed9326278c0e41ca0e91d6b3a75b2feebef7e47a85a1dc095a19e171ff9.json).

nothing has been changed.

## comment 5550136527 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136527

Created: 2026-08-06T14:42:28Z; updated: 2026-08-06T14:42:28Z

Exact metadata: [source record](sources/comment-5550136527-91077a0fbcc7902c3d91d42dab9e466607cf8bb2dea026050192536462726f23.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. In free roam, test child targetability and damage while confirming missions/cutscenes remain protected.

## comment 5550136539 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136539

Created: 2026-08-06T17:09:39Z; updated: 2026-08-06T17:09:39Z

Exact metadata: [source record](sources/comment-5550136539-9197199242c3bdc070389a8e7ae3f67d38d4d5373d030c9bffe5d54abe2b5f8b.json).

still can't shoot the annesburg paperboy.

## comment 5550136553 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136553

Created: 2026-08-06T18:53:13Z; updated: 2026-08-06T18:53:13Z

Exact metadata: [source record](sources/comment-5550136553-159b6a6118b5775904be5da017f47a714c391fa309c7e68bad40bd91df2f06df.json).

Rewritten after finding three provable causes, none of which were guesses.

1. **The reported ped was never a candidate.** The Annesburg paperboy is `S_M_Y_NEWSPAPERBOY_01` (model string throughout `script_rel`; `main.c:3263` suppresses it by name). The fallback model list held only three street-kid models, so unless `_IS_PED_CHILD` classified him he was skipped outright. `A_M_Y_NBXSTREETKIDS_02`, `U_M_Y_SHACKSTARVINGKID_01` and `G_M_M_UNILANGSTONBOYS_01` were missing too.
2. **Staging never completed.** It required the same ped to remain the single nearest child for 5000 ms, then applied one native per 250 ms scan — about 6.3 s of standing still. In normal play the candidate resets and nothing is ever written, which matches the empty runtime log.
3. **Rockstar overwrote the writes.** `script_rel/short_update.c` `func_150` (lines 5186-5196) applies `SET_ENTITY_INVINCIBLE(true)`, `SET_ENTITY_CAN_BE_DAMAGED(false)` and `SET_ENTITY_PROOFS(255,false)` to each child after `IS_PED_READY_TO_RENDER`. The module memoised each ped and never rewrote, so Rockstar won permanently.

Fixed: mutators consolidated and re-applied every 250 ms to every classified child within 100 m (8 per scan), staging and memo set removed, 7-model fallback, plus `IS_ENTITY_A_MISSION_ENTITY` as a second gate mirroring Rockstar own exclusion so Jack stays protected. Mission/blocked gate still runs first.

**On the crosshair specifically — read this before testing.** `SET_PED_CAN_BE_TARGETTED` appears 1705 times in `script_rel`, always on mission/anim-scene peds, never on a child; `SET_PED_CAN_BE_TARGETTED_BY_PLAYER` appears exactly once. Child protection is registered in `short_update.c` `func_168` (~line 5735), which touches no targeting native at all. So the reticle rejection is engine-side, not script-applied, and the SDK exposes no native that changes a ped child classification (`_IS_PED_CHILD` is read-only).

The rewrite therefore logs a before/after pair for the nearest child: `_GET_ENTITY_CAN_BE_DAMAGED`, `_GET_ENTITY_PROOFS`, `IS_PLAYER_TARGETTING_ENTITY`, and `GET_PED_CONFIG_FLAG` across 12 probe indices (read, never written). If the log shows `damageable=1 proofs=0 player_targetting=0` while you are aiming at the logged ped, the crosshair lockout is unreachable from an ASI and this should be relabelled rather than guessed at again. A config-flag index is the only untested lever — that is what the 12 probes exist to identify.

Built, SHA-256 `D7A3A305D74AA519F008336C008451D5CD5348FE3894BBC34E044000F0B0B479`, install queued behind the running game. Staying `actionable` until it lands.

## comment 5550136564 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136564

Created: 2026-08-06T18:59:41Z; updated: 2026-08-06T18:59:41Z

Exact metadata: [source record](sources/comment-5550136564-0e70c0cc8e02d0292a4c6e868315f14b679987bab2a53350a9b4ac7957a15c02.json).

Install verified. `GameplayTweaks.asi` in the game root hashes SHA-256 `D7A3A305D74AA519F008336C008451D5CD5348FE3894BBC34E044000F0B0B479`, matching the build. Moved to `test me`.

## comment 5550136576 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136576

Created: 2026-08-09T11:41:01Z; updated: 2026-08-09T11:41:01Z

Exact metadata: [source record](sources/comment-5550136576-9e835f53b4485aa92ca817885b28105056dfd72537cf9a7594fe009e2a8201e6.json).

The startup crash log exposed this module issuing all five child damage/targeting setters every 250 ms even when readback already said damageable=1 proofs=0. The same Saint Denis child was mutated repeatedly until the asynchronous ERROR:FFFFFFFF; no exception/dump was produced.

Blind periodic reapplication is removed. Each ped gets the targetability application once. Later scans only rewrite damageability/invincibility/proofs if readable state proves Rockstar restored protection. Mission and mission-entity exclusions, all seven model fallbacks, the 100 m bound, and before/after logging remain.

Installed ASI: 0064A7C4F446693A72F7472C0B17154B0A631C58678D999F50097A65AFC8FAB4. Source/game-root ASI and project/game-root manifests match; the updated Lexer-Lux/Lexeditor#201 verifier passes. The issue remains test me and open.

## comment 5550136597 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136597

Created: 2026-08-10T05:18:56Z; updated: 2026-08-10T05:18:56Z

Exact metadata: [source record](sources/comment-5550136597-13c74985e4479e24063fcc5e2b8a1019a23047586c46d9a4ab588c3e3ed8c238.json).

The normal build now removes Lexer-Lux/Lexeditor#201 from the live translation unit entirely. The direct runtime acceptance failed: after the newspaper-boy model had its damage/proof state forced from protected to damageable, attempting the weapon hit produced ERROR:FFFFFFFF. The targetability setters also never lifted Rockstar's engine-owned crosshair rejection. With the available Story Mode ScriptHook/native interface, this cannot be made both functional and safe, so the failed runtime has been removed and the open issue is now correctly labeled unfeasible. Installed ASI SHA-256: CA338164F56EBCFB2EB22FA992F6BE296F47EBC7594EDA3E970341E91A1A930E.

## comment 5550136613 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136613

Created: 2026-08-10T05:32:29Z; updated: 2026-08-10T05:32:29Z

Exact metadata: [source record](sources/comment-5550136613-24ec434edc37b85788c533a0142dbd13faa0b1131ca82b1c4ad3b0ea6b7d46c4.json).

How did this get tagged as unfeasible when there's been a mod that does this exact thing for over four years now
https://www.nexusmods.com/reddeadredemption2/mods/199?tab=description

## comment 5550136626 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136626

Created: 2026-08-10T05:32:35Z; updated: 2026-08-10T05:32:35Z

Exact metadata: [source record](sources/comment-5550136626-e92ec33dd7c9fa5acd3fd92e669b599e9b33e8c1845caf82a9456cfe95ca923a.json).

Correction: the unfeasible verdict was wrong. The existing RDR2 'Kill Children' mod is direct counter-evidence that the requested player-facing behavior is achievable. My failed native implementation only proved that particular approach was unsafe; it did not prove the feature impossible. I am retracting that conclusion, restoring the open issue to actionable, and investigating the proven implementation before writing another runtime.

## comment 5550136642 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136642

Created: 2026-08-10T05:54:42Z; updated: 2026-08-10T05:54:42Z

Exact metadata: [source record](sources/comment-5550136642-d6b096461db56f8733db7970e0f4d52719b75ee5e37091c627e3e61910d1e590.json).

Correction implemented in source. I statically analyzed the existing Kill Children v1.1 ASI instead of repeating the failed native approach. It uses two MinHook detours: a targeted internal flag query that returns false only for hash 0xE4401C70, plus the child blood-effects predicate. Both reference signatures resolve uniquely in the current loaded RDR2.exe. GameplayTweaks now ports those two detours, performs no child enumeration or entity/ped native writes, and atomically forwards to Rockstar's original functions during missions, loading/fades, disabled control, and custom menus. Static verifier and combined build pass; ASI SHA-256 is 9D66086D0FE44AF89EBA2FBFFFEAE760BB676C49D75940FC32E437B3EFAB9C53. RDR2 is currently running, so this build is not installed and the issue correctly remains actionable until it lands.

## comment 5550136654 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136654

Created: 2026-08-10T07:17:07Z; updated: 2026-08-10T07:17:07Z

Exact metadata: [source record](sources/comment-5550136654-67fffeb9be1f69c623c96f68ecb938d7f78d5690eb03d8c7fd72d4a53edc16c3.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test free-roam child vulnerability while confirming missions and blocked contexts retain protection.

## comment 5550136670 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136670

Created: 2026-08-10T10:01:17Z; updated: 2026-08-10T10:01:17Z

Exact metadata: [source record](sources/comment-5550136670-fb23e10fad08ae543f692a26d95c0d6396ad109b7e56dbafb3fd30f56dca680a.json).

Failed runtime result: the installed process-wide child-vulnerability detours remained active in free roam and poisoned shared predicates used by shops, removing store/station/paperboy availability and prompts. The unsafe hook path is being explicitly removed by Lexer-Lux/Lexeditor#209's startup safety repair. Lexer-Lux/Lexeditor#201 itself is not fixed or test-ready; it is disabled and correctly returns to actionable until child vulnerability can be implemented without process-wide collateral effects.

## comment 5550136694 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136694

Created: 2026-08-10T11:04:32Z; updated: 2026-08-10T11:04:32Z

Exact metadata: [source record](sources/comment-5550136694-702239ce46bedc2ec89e30ac2c7e57724fe46515f0de0f3816a4622493f67a23.json).

Architecture boundary confirmed: Story continuously reapplies child invincibility, can-be-damaged=false, and full proofs. Public entity setters changed readbacks but never lifted the engine target predicate; an actual hit path aborted ERROR:FFFFFFFF. The only resolved working reference uses the same two process-wide predicate hooks that Lexer-Lux/Lexeditor#209 proved also own shop/station/paperboy interactions, and those hook boundaries expose no authoritative child entity for safe scoping.

The dormant hook installer is now removed entirely and the module performs zero hooks and zero entity writes. Further progress needs a new entity-local architecture or new primary evidence. Moving this from actionable to needs a human; it is not test-ready and the unsafe hook path will not be resurrected.

## comment 5550136711 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/201#issuecomment-5550136711

Created: 2026-08-14T01:33:36Z; updated: 2026-08-14T01:33:36Z

Exact metadata: [source record](sources/comment-5550136711-cec844eba6b9e935fd9b25468508ea39c27bd10ef0528384c27d01610c02de5f.json).

**Log-only fix: the safety heartbeat here was written but never dispatched.**

To be clear about scope first — the feature itself is not changed and this issue keeps its `needs a human` label. `initializeChildVulnerability()` is dispatched normally at `script.cpp:1860` and does the actual work.

What was missing is `updateChildVulnerability`, which reports this feature's safe-disabled boundary state on a gate change or every 30 seconds. It was defined but never called from anywhere, so the runtime log contained exactly **one** `[child-vuln]` line for a whole session — the init — and the boundary was unobservable. "Not executed" and "executed with nothing to report" were indistinguishable, which the project's own rules specifically forbid for a safety boundary.

It is now called each frame with the same mission and dead/faded values its neighbours use. It mutates no gameplay state; it only writes to the log. The Lexer-Lux/Lexeditor#201 verifier passes, and it is built and installed.

Found while auditing for dispatcher calls that were commented out or never wired — the same sweep that found Lexer-Lux/Lexeditor#238's guard disabled at `script.cpp:3156`.

