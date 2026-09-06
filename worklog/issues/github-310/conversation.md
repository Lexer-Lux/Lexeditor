# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356483581 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310

Created: 2026-08-29T15:07:03Z; updated: 2026-09-05T07:39:30Z

Exact metadata: [source record](sources/issue-5356483581-018562c9d87b99c191b01b9d168f9107254b52aeaf866497133f9ecfb559cf44.json).

Add a Shared Party Magic Inventory boolean setting to the FF8 Settings tab. Default: off.\n\nWhen enabled, the party uses one shared stock of spells instead of one 32-slot stock per character. The implementation must cover field menus, Draw gains, casting/consumption, transfers, battle reads, and junction-stat quantity reads. It must not be a display-only synchronization.\n\nThe patch must use verified FF8/FFNx engine paths and preserve vanilla behavior when disabled. Static checks must identify each covered read/write boundary. Player acceptance must confirm Draw, casting, junction stats, menu display, and inactive/active party changes use the same stock without duplication or loss.

## issue 5356483581 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310

Created: 2026-08-29T15:07:03Z; updated: 2026-09-06T12:59:31Z

Exact metadata: [source record](sources/issue-5356483581-c587cdd4133608cec4437aa5b9de63b16a28fa105448b4559dea312e52d16d72.json).

Use one saved spell pool for menus, Draw, casting and junction quantities, without loss or duplication. Reject migration cleanly when existing stocks cannot fit.

**Status: The runtime is packaged, but a completed in-game handoff is not recorded.** Prepare copied-save migration/overflow tests and verify the installed driver. Party Switch (#313) and non-100 stock caps (#94) remain unfinished combinations.

## issue 5356483581 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310

Created: 2026-08-29T15:07:03Z; updated: 2026-09-06T12:59:31Z

Exact metadata: [source record](sources/issue-5356483581-e05442183db02bfaa0f2842e0626771cdba46ec8ffc113e27f468421c1cf0849.json).

Use one saved spell pool for menus, Draw, casting and junction quantities, without loss or duplication. Reject migration cleanly when existing stocks cannot fit.

**Status: The runtime is packaged, but a completed in-game handoff is not recorded.** Prepare copied-save migration/overflow tests and verify the installed driver. Party Switch (#313) and non-100 stock caps (#94) remain unfinished combinations.

## comment 5550344330 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310#issuecomment-5550344330

Created: 2026-08-29T15:14:55Z; updated: 2026-08-29T15:14:55Z

Exact metadata: [source record](sources/comment-5550344330-334620c6ccf49420bed7dbd48f8a02ad4f2b622b7f1ddff967a0e5650b64526f.json).

This is feasible, but it needs an FFNx-side shared-stock feature. FF8 has eight fixed 32-slot inventories, and the executable reads them directly across menus, battle, Draw, and junction calculations; one Hext address change cannot cover them safely. I need one rule before I can finish it: when shared mode first turns on, combined private stocks can exceed 100 copies of a spell or 32 distinct spells. Should Lexeditor refuse to enable shared mode until the player reduces the stocks to a lossless 32-slot/100-copy merge, or should it merge and discard the excess? I will not silently delete or duplicate magic.

## comment 5550344347 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310#issuecomment-5550344347

Created: 2026-08-29T15:18:22Z; updated: 2026-08-29T15:18:22Z

Exact metadata: [source record](sources/comment-5550344347-596ee603ebdb255f7dde41e0124b2d7a5e2f8de1d966ef59be008799b6f59dea.json).

Decision: Shared Party Magic Inventory stays enabled when selected, but the runtime does not merge inventories until the existing stocks fit one 32-slot pool with no spell above 100 copies. Until then, FF8 shows a clear in-game warning and leaves every private inventory unchanged. The implementation must never cap, discard, or duplicate magic.

## comment 5550344356 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310#issuecomment-5550344356

Created: 2026-08-30T19:39:18Z; updated: 2026-08-30T19:39:18Z

Exact metadata: [source record](sources/comment-5550344356-56353f6c7c81c4a9298cfcc9c72d1f6aa38d1dba5c44c9bc49a8bbc9d327dea7.json).

The Shared Party Magic Inventory setting is still absent because no runtime implementation was completed. It must not be presented as done. Continue with the previously decided lossless-migration rule and expose the toggle only with a real covered stock path.

## comment 5550344368 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310#issuecomment-5550344368

Created: 2026-08-30T20:30:56Z; updated: 2026-08-30T20:30:56Z

Exact metadata: [source record](sources/comment-5550344368-c4b87e30a8e03fbf31dcafd934184fc7194773094c72d29643d1e84b4e4fc18c.json).

The lossless shared-stock core and migration warning contract now build and test, but the runtime feature remains fail closed. The executable has at least 271 direct magic-array references, and official FFNx evidence resolves only three helpers—not ownership across field menus, Draw award, battle consumption, transfer, junction, and party redistribution. Exposing a partial toggle would still duplicate or lose stock.

## comment 5550344380 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310#issuecomment-5550344380

Created: 2026-08-31T05:29:58Z; updated: 2026-08-31T05:29:58Z

Exact metadata: [source record](sources/comment-5550344380-343c225b514a341713bb543cb3cfec912f6cd8f70a69d1562da2c91f57401389.json).

Confirmed: this remains unmade, not merely missing from the Tweaks UI. Lexeditor currently has only the tested lossless merge/stock core; the runtime module is not registered, and the enabled build path deliberately fails closed.

I also checked current official FFNx head. It still exposes eight private `magics[32]` arrays and no shared-stock ownership boundary or external gameplay-module loader. A real implementation therefore still needs a custom FFNx/engine patch covering menu display and edits, Draw gains, battle reads and consumption, transfer, junction quantities, party redistribution, lossless migration, and the blocker warning. I did not add a checkbox that would silently do nothing. This remains actionable.

## comment 5550344390 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310#issuecomment-5550344390

Created: 2026-08-31T11:31:04Z; updated: 2026-08-31T11:31:04Z

Exact metadata: [source record](sources/comment-5550344390-ac32538b5c59a9006cc89ae5b92205a2560d0df7ae302930f7d936c8aabed8db.json).

I expanded the executable audit: the supported FF8 build has 271 direct Magic references, including 50 direct writes in 12 clusters, plus four additional same-block derived reads. Cross-block derived accesses remain unclassified. I also built and then rejected an event-driven page-protection prototype. Mirroring one pool into eight arrays could make aggregate readers see 8x stock, corrupt two-step transfers after the first write, trap unrelated state on the same 4 KB page, and race during teardown; its Win32 dialog was not the required FF8 warning. I deleted that prototype and kept the enabled path fail closed. The stronger verifier and lossless x86 core tests pass, but the full FFNx ownership abstraction is still required, so this remains actionable.

## comment 5550344400 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310#issuecomment-5550344400

Created: 2026-08-31T12:19:13Z; updated: 2026-08-31T12:19:13Z

Exact metadata: [source record](sources/comment-5550344400-2e11fe3af6acfdcf7c2112cbdece28fb2dc058c27a40eff8a1530447d6dc5eff.json).

Resolved the persistence model and several runtime boundaries. Shared mode can use character zero's existing 32-slot array as the sole saved pool, with an atomic lossless merge after the verified save-map copy. Characters keep their own junction spell IDs; junction calculations must read quantities from the shared pool. I also resolved the four stock add/remove primitives, the final Draw award, transfer range, junction quantity range, redistribution calls, and the existing FFNx save wrapper.

This removes the unsafe mirror/page-trap design. The feature still remains fail closed while the Magic-menu and battle read sites are classified and while the new-game and native FF8 warning-window lifecycles remain unproved. No inert toggle has been added; the issue remains actionable.

## comment 5550344411 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/310#issuecomment-5550344411

Created: 2026-08-31T17:07:21Z; updated: 2026-08-31T17:07:21Z

Exact metadata: [source record](sources/comment-5550344411-0e7670bd196b517b3a0252b8f426f784b53439870c9941fb7cc61d3e808c25eb.json).

The complete shared-Magic runtime is now packaged and connected to the Tweaks setting. It uses one strict per-mod setting, installs 28 guarded function hooks plus four guarded call-site patches, performs an atomic lossless migration, and shows the native warning when existing stocks cannot fit. The package, rollback, source-mutation, binary-mutation, and no-deploy checks pass; no game file was installed and FF8 was not launched.

Please test it in-game after installing the managed derivative through Lexeditor:

1. Enable Shared Party Magic Inventory on a save whose combined stocks exceed 32 spell types or 100 copies of one spell. Confirm the FF8 warning appears and all private stocks remain unchanged.
2. Reduce the stocks, enable it again, and confirm the migration succeeds.
3. Confirm the same pool is used by the menu, Draw, casting, junctions, transfers, and party changes.
4. Confirm scenario transitions, save/reload, and a new game do not duplicate or lose Magic.
5. Check FFNx.shared-magic.log for requested=1, 28 installed function hooks, four installed call-site patches, continuing heartbeats/hit counters, and no failure record.
