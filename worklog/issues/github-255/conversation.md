# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356321235 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/255

Created: 2026-08-10T15:47:08Z; updated: 2026-09-05T07:03:13Z

Exact metadata: [source record](sources/issue-5356321235-d84231b6105628906ca8de531c4f8972a288e2d8f25ebdb393eb62ab95cf35e6.json).

<img width="534" height="243" alt="Image" src="https://github.com/user-attachments/assets/2364bde4-05d7-4c76-b294-1c64ee45893a" />

## issue 5356321235 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/255

Created: 2026-08-10T15:47:08Z; updated: 2026-09-06T13:31:55Z

Exact metadata: [source record](sources/issue-5356321235-d32b6f028f9a51f2dfc4a4785a55fe890f15476ec41a3259b39790d9a5baf368.json).

**Closed after the installed repair.** The replacement uses a valid help message and handles physical camps without guessing which saved marker to erase. Current campsite behavior remains in #101.

[Original report image](https://github.com/user-attachments/assets/2364bde4-05d7-4c76-b294-1c64ee45893a).

## comment 5550151637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/255#issuecomment-5550151637

Created: 2026-08-10T16:38:07Z; updated: 2026-08-10T16:38:07Z

Exact metadata: [source record](sources/comment-5550151637-48e85ec7dc84d79523e6bb27a95d6734d910a6d7019e04d273102846ab687bec.json).

I recovered the screenshot and traced both consecutive failures. The address shown in the ScriptHook dialog is the ASI's registered entry address, not the faulting instruction. The actual crash repeated at the same `RDR2.exe+0x25F799A` address twice.

In the second run, the last successful event was the F3 campsite hold. The very next statement called Rockstar's cleanup native using the ScriptHook-returned `player_camp` **thread ID**; nothing after it logged. The crash trace still said `updateProjectileVisibility` only because there was no newer stage marker before campsite handling.

I replaced that exact thread-ID cleanup call at both campsite removal and site switching with Rockstar's separate name-addressed cleanup for the exact `player_camp` owner, retaining its authored cleanup flag 555. I also added a real `updateCampsites` crash stage so a future fault cannot inherit the projectile label again.

Lexer-Lux/Lexeditor#255 remains `actionable` until this is compiled and installed. After installation, both F3 hold-removal and F3 tap-creation still need real in-game confirmation; a thread-start line or CSV write will not be treated as proof that the physical camp appeared.

## comment 5550151661 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/255#issuecomment-5550151661

Created: 2026-08-10T17:01:23Z; updated: 2026-08-10T17:01:23Z

Exact metadata: [source record](sources/comment-5550151661-f42f7e1f5aeb0bd3913fa3be968b21b0d7f20bd297141d739a893a55c393c36d.json).

The campfire crash repair is installed. Campsite removal/switching no longer passes ScriptHook's returned player_camp thread ID into the crashing cleanup call; it uses Rockstar's name-addressed cleanup for that exact script owner, and campsite handling has its own crash-stage marker. Test F3 hold-removal, then F3 tap-creation; success requires the physical camp and saved state, not merely a thread-start log.

## comment 5550151674 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/255#issuecomment-5550151674

Created: 2026-08-10T18:04:48Z; updated: 2026-08-10T18:04:48Z

Exact metadata: [source record](sources/comment-5550151674-d17aa306cb5cf0cf854d1da87dae96a5b030b9e1a07ce12bc8b0c148c2ee0548.json).

Returned runtime failure: holding F3 immediately crashed GameplayTweaks again.

This time the preserved trace is definitive: `code=0xC0000005`, `RDR2.exe+0x25F799A`, stage `updateCampsites`. The last completed line is `removal-hold ... sites=15 nearest=-1`. Because `nearest=-1`, the repaired name-addressed `player_camp` cleanup branch was not entered at all. The next operation is the newly added `campMessage("Stand at an authored campsite to remove it.")` tooltip call, so the previous diagnosis was incomplete and the installed candidate failed.

I am moving only Lexer-Lux/Lexeditor#255 back from `test me` to `actionable`. Closed Lexer-Lux/Lexeditor#211/#149 remain closed, and Lexer-Lux/Lexeditor#101 explicitly tracks different camp-kit/teardown-prompt behavior. I am removing the crashing notification path and will not call this repaired again until the replacement is compiled, installed, and its exact crash boundary is instrumented.

## comment 5550151694 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/255#issuecomment-5550151694

Created: 2026-08-10T18:11:27Z; updated: 2026-08-10T18:11:27Z

Exact metadata: [source record](sources/comment-5550151694-2761c44530d0e249c0e5acde622cd8e736631d081b4d9dbeb518960de9dac1ec.json).

Installed replacement for the returned F3 crash.

The failed run proved the cleanup branch never executed (`nearest=-1`). The crashing next operation was the new help-text notification, which passed arbitrary English directly where Rockstar's own wrapper supplies a GXT label or `_CREATE_VAR_STRING` result. The installed wrapper now constructs a supported literal var-string, skips the feed entirely if construction fails, and records separate `campMessage.createLiteral` / `campMessage.showTooltip` crash stages.

The same run also proved saved-coordinate matching failed: Arthur's live camp position was about 159 m from the nearest saved Valentine origin. F3 now recognizes a nearby exact `P_CAMPFIRE02X_COMBO` only when `player_camp` itself has a live script reference. It removes the associated transient row when known; after a restart, when that transient association is gone, it cleans up the exact physical `player_camp` but deliberately does not guess and erase an unrelated saved marker.

Please repeat exactly the failed action: start at that camp and hold F3. Acceptance is: no ScriptHook exception, the physical camp disappears, and the new log identifies whether a saved row was removed or preserved. This is installed but not yet runtime-accepted, so Lexer-Lux/Lexeditor#255 is moving to `test me`.
