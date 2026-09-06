# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5288664916 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59

Created: 2026-08-29T20:21:06Z; updated: 2026-09-05T08:14:58Z

Exact metadata: [source record](sources/issue-5288664916-5b1ea41d68f97e7594c5116b680c5d34115cf71a15b5e6345f3668d6b41b27b1.json).

Keep an opened game plugin resident while the shared main menu is visible.

Requested behavior:
- Entering a newly loaded plugin pans the shared surface to the right.
- Returning home pans left to the game menu without stopping the child service.
- A right-edge resident-plugin handle remains visible on the menu; selecting it pans back to the live plugin without starting or loading it again.
- Loading a plugin from its box-art card shows a brief per-game quote screen while the child starts.
- Returning through the resident handle does not show the loading quote.
- Quotes are stored in one editable JSON file by game ID.
- Starting another game may replace and stop the previous resident session.
- Existing dirty-change confirmation still applies before leaving an editor.

Acceptance:
- The same child process and session identity survive editor to menu to resident-handle return.
- The menu and plugin transitions visibly pan in opposite directions.
- A new box-art load shows one configured quote; a resident return does not.
- Missing or empty quote lists degrade to a neutral loading screen.

## issue 5288664916 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59

Created: 2026-08-29T20:21:06Z; updated: 2026-09-06T12:38:22Z

Exact metadata: [source record](sources/issue-5288664916-9629e5c94a95b8f583110debb7661b04d3ad973f272b84975c0b1997a3893d77.json).

Return Home and resume the same editor through its right-edge handle without reloading. Fresh loads use the quote screen; navigation pans smoothly and the header stays visible.

**Status: Mostly implemented.** Resident navigation, pan and header repairs are recorded, but loading-message selection is currently broken in #353. Fix that regression before final acceptance of the complete loading flow.

## issue 5288664916 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59

Created: 2026-08-29T20:21:06Z; updated: 2026-09-06T12:38:22Z

Exact metadata: [source record](sources/issue-5288664916-d0c028aed1fb8b3889e0b68591343db7c334cfda6e496fe51ca4e85d5eff5e4b.json).

Return Home and resume the same editor through its right-edge handle without reloading. Fresh loads use the quote screen; navigation pans smoothly and the header stays visible.

**Status: Mostly implemented.** Resident navigation, pan and header repairs are recorded, but loading-message selection is currently broken in #353. Fix that regression before final acceptance of the complete loading flow.

## comment 5464858540 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5464858540

Created: 2026-08-29T21:01:01Z; updated: 2026-08-29T21:01:01Z

Exact metadata: [source record](sources/comment-5464858540-2ffb4a2ce2379df2fbb6d9b4c2ad70413b3211a557408422995bb8b8f0133f2f.json).

Home now keeps the active plugin service in memory and shows its cover-art handle at the right edge. The handle resumes the same service without setup or a quote; a fresh box-art load pans in and displays one random line from the editable per-game JSON file. The one-window host test confirmed the same FF8 process was resumed before another game replaced it.

## comment 5466673394 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5466673394

Created: 2026-08-30T04:21:52Z; updated: 2026-08-30T04:21:52Z

Exact metadata: [source record](sources/comment-5466673394-781aaa0587597bcfdfcf04e16c65a3bf589f1d3f1fd11339a3c37e20fb67d873.json).

Added the supplied RDR loading line to the editable per-game quote data: ‘Billion-dollar idea: RDR spinoff set in the modern day. Who's working on this?’ The existing quote-source contract still passes.

## comment 5471601080 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5471601080

Created: 2026-08-30T22:17:52Z; updated: 2026-08-30T22:17:52Z

Exact metadata: [source record](sources/comment-5471601080-1d2e151b290b49348884655cfacef38899dfbb348f80829ed394ce3aedcf25bd.json).

The transition snapshot now keeps the resident right-edge handle. Both pan surfaces stay on compositor layers, and cleanup waits for a painted destination frame to prevent the start/end flash. The rendered transition kept the handle and completed without a blank surface. Please check the real pan after restarting Lexeditor.

## comment 5471668462 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5471668462

Created: 2026-08-30T22:32:46Z; updated: 2026-08-30T22:32:46Z

Exact metadata: [source record](sources/comment-5471668462-da586f4cc512d0b76aa19a77857c7e288c9868bf60d74f0b7581e129023e8423.json).

Follow-up acceptance: make the resident handle's right arrow materially heavier, and expose the handle width as a percentage-based Lexer default so the packaged width can be tuned for every screen size.

## comment 5471735808 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5471735808

Created: 2026-08-30T22:47:11Z; updated: 2026-08-30T22:47:11Z

Exact metadata: [source record](sources/comment-5471735808-c158aaf4603095adbaca1941620be127715737e1dbd8db68dcee5e28258da9ae.json).

The resident handle now uses a Lexer-owned viewport percentage instead of a fixed pixel width. The packaged default is 5% (bounded from 2.5% to 12%), and the arrow stroke is substantially heavier. The hidden 1440 px render measured the handle at 72 px and retained it through the pan snapshot.

## comment 5471754845 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5471754845

Created: 2026-08-30T22:51:22Z; updated: 2026-08-30T22:51:22Z

Exact metadata: [source record](sources/comment-5471754845-2ccd426ee782ee69f6f66fad02a46997aa4dfac75c3debf28b718a4d2045b30d.json).

Home layering follow-up: the configurable top menu bar must occupy the top layer and the resident-editor handle must begin below it. The handle must never cover the menu bar.

## comment 5471818378 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5471818378

Created: 2026-08-30T23:05:27Z; updated: 2026-08-30T23:05:27Z

Exact metadata: [source record](sources/comment-5471818378-f366a32a19ab2f6f055b1a7bd36b640dcad7a064e7692bee5e87525d01fe4add.json).

The Home menu height now drives both the menu bottom and resident-handle top. A forced-overlap render confirmed that the menu remains the top hit target, so the handle cannot cover its controls.

## comment 5472704921 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5472704921

Created: 2026-08-31T01:48:38Z; updated: 2026-08-31T01:48:38Z

Exact metadata: [source record](sources/comment-5472704921-34b3df849805a219c2af506848998d97570a6fa20788e280d1ec00f691c06bc9.json).

The Home resident handle now reserves 15% of its height at both ends. Its save icon and rotated game title scale with the live handle size. I also corrected >tfw no GF and added the supplied RDR1 and RDR2 loading lines exactly as written.

## comment 5472759657 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5472759657

Created: 2026-08-31T01:57:44Z; updated: 2026-08-31T01:57:44Z

Exact metadata: [source record](sources/comment-5472759657-32d8ba182f6c265e37f628426c55b9766a6d5bd15badf49adddccd517224d65b.json).

Fresh loads now combine the selected game's messages with the global pool. Each game-specific line has weight 1; each global line has weight 1/X. The Lexer-only Global message rarity default is 3. I also added the Arabic shahada to the global pool. Restart Lexeditor before checking because the selector runs in the desktop host.

## comment 5473231686 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5473231686

Created: 2026-08-31T03:13:43Z; updated: 2026-08-31T03:13:43Z

Exact metadata: [source record](sources/comment-5473231686-c3d5888b6e9bf50d7da2396d234880f3b3ded49ae6daba08ee37840d23d4d549.json).

Added the four supplied Blank Game loading jokes as an exact per-game JSON pool. The quote regression also exposed and restored the previously requested Arabic global line. JSON and weighted loading-quote contracts pass.

## comment 5473277831 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5473277831

Created: 2026-08-31T03:20:31Z; updated: 2026-08-31T03:20:31Z

Exact metadata: [source record](sources/comment-5473277831-69b6e4a9d2e3ac43261cf12d1462b9b4fb52c3556b1d21ed24f4d30a379ab037.json).

The all-games open failure came from the Home transition embedding every original cover at full size, then rejecting the combined snapshot above 2 MB. Transition covers are now bounded display thumbnails, and an oversized cosmetic snapshot now degrades without blocking the editor. The real hidden desktop host opened FF8, returned Home, resumed the same FF8 service, then opened RDR successfully. Restart Lexeditor once so the running desktop host loads this repair.

## comment 5473359799 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5473359799

Created: 2026-08-31T03:33:36Z; updated: 2026-08-31T03:33:36Z

Exact metadata: [source record](sources/comment-5473359799-16aed28517273fc3a49cedf23a53fc825de0eb7098899d9e55c6778c26b8f823.json).

The remaining start/end flash had two causes: destination pages could paint before the preserved surface was ready, and the final position depended on a temporary compositor animation. Both Home and editor destinations now wait behind a pre-paint handoff, card/cover surfaces finish loading before reveal, and final transforms are committed before animation cleanup. The FF8 transition render and full hidden desktop-host round trip passed. Please restart Lexeditor and check both directions.

## comment 5473875318 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5473875318

Created: 2026-08-31T04:50:12Z; updated: 2026-08-31T04:50:12Z

Exact metadata: [source record](sources/comment-5473875318-15abdbef283fc3b332cb3bfab2672207eef46931b9574a96fa9792705fe1d19c.json).

Added a Lexer-only Loading screen minimum setting, default 1.5 seconds and adjustable from 0 to 10 seconds. Its clock starts when Home first shows the loading overlay, so plugin/host startup counts toward the minimum; slow loads are never shortened or given an extra fixed delay. A rendered timing test kept the overlay visible after an early finish request and cleaned the temporary transition timestamp afterward.

## comment 5482423574 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5482423574

Created: 2026-08-31T18:05:00Z; updated: 2026-08-31T18:05:00Z

Exact metadata: [source record](sources/comment-5482423574-14ebc62a92ca9393924b3dd52f47c5d7f90f4f210f98f6c821b47c526575d31d.json).

Refined both transition boundaries. The loading dim now fades in, and the pan keeps its settled transform through two painted destination frames before removing the animation layer. Home window controls sit over the full-height resident handle at 50% opacity and brighten on hover. The loading-minimum timing check and rendered Home transition check pass; please restart Lexeditor and check both pan directions for the remaining native-window flicker.

## comment 5541451025 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5541451025

Created: 2026-09-04T13:54:12Z; updated: 2026-09-04T13:54:12Z

Exact metadata: [source record](sources/comment-5541451025-69eb4df4bcaf27e129f0e68652078cf630e987f5be497edd1f26a73b1b3d3ccb.json).

Reduced the resident-handle arrow from the over-heavy stroke and corrected the title layout. The game name now uses a true centre anchor in a reserved lower region, while the arrow sits above it. The rendered Home check measured no overlap and kept handle-width and save-icon scaling intact. Restart Lexeditor before checking it.

## comment 5550024709 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5550024709

Created: 2026-09-05T06:38:02Z; updated: 2026-09-05T06:38:02Z

Exact metadata: [source record](sources/comment-5550024709-75e0b0d7069ae16e25c9c01ae689fa0ec975f7269a0a44c01456e7aa137b72b4.json).

The main menu now uses the existing full-screen quote and spinner while game data and cover images load, including the configured minimum display time. The small Loading plugins text is removed. Refreshes keep already-loaded covers, and a failed refresh shows a retry dialog without clearing the tiles. Rendered delayed-load, image-ready, refresh/error, and loading-duration checks passed. Restart Lexeditor to see the main-menu startup change.

## comment 5550257532 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5550257532

Created: 2026-09-05T07:21:45Z; updated: 2026-09-05T07:21:45Z

Exact metadata: [source record](sources/comment-5550257532-ff4eb400875118e4701bcb4f8118565ecfb4c21d0284e803108cbf96675424cb.json).

Removed the hard-coded main-menu loading phrase. Startup now uses a message from the global pool in the existing loading screen. The rendered startup check confirms that the selected message appears before the game tiles are revealed.

## comment 5550522078 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/59#issuecomment-5550522078

Created: 2026-09-05T08:14:58Z; updated: 2026-09-05T08:14:58Z

Exact metadata: [source record](sources/comment-5550522078-933d73c4c0485ec042a3b286748eb043102673db2660f2330bcb8fe86fb71f93.json).

Fixed the shared transition wrapper that caused the menu bar to scroll out of view after entering a plugin. The header and tabs now remain at the top while the page scrolls. Rendered RDR2 checks passed after the entry transition at two scroll depths; the loading-duration check also passed.
