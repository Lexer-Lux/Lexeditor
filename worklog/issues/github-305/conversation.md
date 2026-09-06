# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356482788 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305

Created: 2026-08-30T20:50:36Z; updated: 2026-09-05T16:11:35Z

Exact metadata: [source record](sources/issue-5356482788-c145c696aead48831f4810d79f0bae17ebd1df5fc389c85e4b74bcd9502999ae.json).

Use the right stick to rotate the world-map camera left and right, with speed proportional to stick movement and a dead zone to prevent drift.

Implemented and confirmed working in game by Lexer.

Vertical movement remains #329. Battle controls remain #330.


## issue 5356482788 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305

Created: 2026-08-30T20:50:36Z; updated: 2026-09-06T13:18:57Z

Exact metadata: [source record](sources/issue-5356482788-fb9831ff5f898cebea14e5362873daa103a175418a47b1188bfee08776fe3bd5.json).

**Status: Confirmed working in game and closed.** Right-stick deflection controls horizontal rotation speed, with a dead zone and no unintended movement or zoom. Vertical camera research is #329; battle controls are #330.

## comment 5550343527 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305#issuecomment-5550343527

Created: 2026-08-31T05:18:47Z; updated: 2026-08-31T05:18:47Z

Exact metadata: [source record](sources/comment-5550343527-dd2dd8cbea39931b96694485e300528f862bb069041e8947bf688562906f6e26.json).

Runtime result: Modern Controls does not work. The setting was enabled, the generated Hext contained the camera patch, FFNx loaded that exact file, and the same session entered the world map several times. This rules out saving and patch loading. The existing static check only proves that one memory read changed from right-stick Y to X; it does not prove that the destination controls the live camera. I have returned this to actionable. The repair must trace the live camera consumer and prove partial/full speeds plus no center drift in-game.

## comment 5550343541 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305#issuecomment-5550343541

Created: 2026-08-31T08:55:50Z; updated: 2026-08-31T08:55:50Z

Exact metadata: [source record](sources/comment-5550343541-62d68be6cd3a739a3e11d790c17df917218d2d752e171e4ca17b819d4a1817a4.json).

The failed special-mode read has been removed. The generated patch now hooks the normal world-map camera axis, uses FFNx's dead-zone-filtered right-stick X magnitude, and leaves the native shoulder value unchanged while the stick is centered. The active C:\FF8Mod patch was regenerated, and the combined patch checks pass. Please test slight and full deflection in both directions, center drift, and the shoulder controls. I have not marked the in-game result complete.

## comment 5550343552 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305#issuecomment-5550343552

Created: 2026-09-04T15:17:58Z; updated: 2026-09-04T15:17:58Z

Exact metadata: [source record](sources/comment-5550343552-cc731852af04d003735adf45652b7fdd377fcf30bc66b76424800195c5f61f8d.json).

Live test disproved the replacement hook. Right-stick input sometimes changed zoom and sometimes moved sideways or forward/back, so the patched field is a state-dependent world-map input field, not stable camera yaw. Modern Controls is disabled again. The next implementation will hook the game's final regular camera-rotation consumer and must leave movement and zoom unchanged.

## comment 5550343570 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305#issuecomment-5550343570

Created: 2026-09-04T15:23:58Z; updated: 2026-09-04T15:23:58Z

Exact metadata: [source record](sources/comment-5550343570-d4a5d74b0bce9a1cfad53836a24a10473d17628b2187df33b97265d7c2907fcf.json).

The replacement now hooks FF8's final regular world-map yaw instruction at 0x00558676 and adds only right-stick X to the camera tangent. The old mixed movement/zoom field is banned from generated patches. Modern Controls is enabled again in Lexer's Mod and the active composed patch contains the new yaw hook. Please test centered, slight, and full left/right stick input on foot; zoom and forward/back movement must remain unchanged.

## comment 5550343578 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305#issuecomment-5550343578

Created: 2026-09-04T15:48:58Z; updated: 2026-09-04T15:48:58Z

Exact metadata: [source record](sources/comment-5550343578-c2a103bc0d3114a68352a80af74d6b9b279531c27d63a0b1f0adcb96f3a8e804.json).

Live test also disproved the final-tangent patch. Right-stick input still causes inconsistent zoom and movement, so the 0x00558676 write is not a safe independent yaw boundary in all world-map states. Modern Controls is disabled in Lexer's Mod and the active runtime. The replacement must use a verified camera-only path or remain unavailable.

## comment 5550343590 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305#issuecomment-5550343590

Created: 2026-09-04T15:51:29Z; updated: 2026-09-04T15:51:29Z

Exact metadata: [source record](sources/comment-5550343590-792b3538722d84d120e5417252c7aa3dcf2d5dcf10c3486e2db13fabd43c8633.json).

The second replacement is disabled and cannot be re-enabled. The right-stick value was correct, but the hook at `0x00558676` runs only in one conditional camera branch; FF8 uses different writers in other world-map camera states. That is why one arithmetic test passed while the live behavior still changed with the camera state. The selected mod and active patch now leave world-map input unchanged. The next implementation must run after the complete camera update, not inside one branch.

## comment 5550343601 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305#issuecomment-5550343601

Created: 2026-09-05T06:38:59Z; updated: 2026-09-05T06:38:59Z

Exact metadata: [source record](sources/comment-5550343601-1b5c8081f29feaae7278dddba29160ce2f7b5c806139cbd1cabc813ea4cec447.json).

Lexer confirms that the earlier version did rotate left/right, although it sometimes also zoomed, and now the stick does nothing. The current implementation explicitly disables Modern Controls and rejects its patch; this loss of input was introduced by that disable, not established as a controller problem. Preserve the observed partial success as repair evidence. Restore proportional left/right camera rotation while removing unintended zoom/movement, and make unavailable state clear in the editor. Work remains deferred at the user's budget boundary; no new test or implementation started.

## comment 5550343614 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/305#issuecomment-5550343614

Created: 2026-09-05T06:51:15Z; updated: 2026-09-05T06:51:15Z

Exact metadata: [source record](sources/comment-5550343614-82c8be65867ef3eae292912dab895d290cba7f74229b7dde49e4bb48264e9495.json).

Clarified camera requirement: world-map left/right rotation must be proportional to stick deflection, not a binary on/off input. Small deflection must rotate slowly, full deflection faster, centered input must not drift, and neither movement nor zoom may be changed. Modern Controls work so far concerned camera movement only; the current implementation is disabled. Vertical analog movement is being tracked as a feasibility sub-issue. Deferred.
