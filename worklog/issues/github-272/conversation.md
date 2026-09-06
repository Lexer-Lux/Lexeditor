# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356326236 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272

Created: 2026-08-11T04:37:34Z; updated: 2026-09-05T07:04:05Z

Exact metadata: [source record](sources/issue-5356326236-19580aa8a76c78cdd7dc05252b276830ba10723ebed701cd936243fede014201.json).

<img width="1784" height="1426" alt="Image" src="https://github.com/user-attachments/assets/96d65a03-6274-4478-9b89-4efc0aa4ab19" />

Even when you try to follow their map marker they're way too hard to find. What can we do to make them more visible in the game world?

## issue 5356326236 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272

Created: 2026-08-11T04:37:34Z; updated: 2026-09-06T13:31:59Z

Exact metadata: [source record](sources/issue-5356326236-c514ef3bb06b906c1c499d3776264bcf7d8ca380532b1548e59ced1759cba619.json).

Inactive camps need black smoke; active camps need white smoke, with one plume per site and clean removal.

**Actionable — latest timing repair is source-only.** The one-second initialization delay was reduced, but the change is not installed. No new timing test is ready.

[Original screenshot](https://github.com/user-attachments/assets/96d65a03-6274-4478-9b89-4efc0aa4ab19).

## issue 5356326236 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272

Created: 2026-08-11T04:37:34Z; updated: 2026-09-06T13:31:59Z

Exact metadata: [source record](sources/issue-5356326236-ef31d7cab098ffdf66c9892de8559d61143130dc00034b2b06c7904cce2c364e.json).

Inactive camps need black smoke; active camps need white smoke, with one plume per site and clean removal.

**Actionable — latest timing repair is source-only.** The one-second initialization delay was reduced, but the change is not installed. No new timing test is ready.

[Original screenshot](https://github.com/user-attachments/assets/96d65a03-6274-4478-9b89-4efc0aa4ab19).

## comment 5550159185 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159185

Created: 2026-08-11T07:13:39Z; updated: 2026-08-11T07:13:39Z

Exact metadata: [source record](sources/comment-5550159185-c441a5bb4d85acd75bfbc9c3601b8e2fb04bdb7da66662ce3bdc8c4d4454316f.json).

The screenshot and source show that the campsite exists, but its inactive object is too hard to see. The image shows the `Activate Campsite` prompt in an ordinary wooded clearing, with no clear fire, smoke, glow, decal, or landmark. That prompt can appear only when the real `P_CAMPFIREBURNTOUT02X` handle exists and Arthur is within five metres. This is a visibility defect, not a missing-placement defect.

Rockstar already has a suitable world cue. `player_camp.c` uses particle asset `scr_distance_smoke` and looped effect `scr_campfire_distance_smoke_script` at the camp origin. Several ambient-camp scripts use the same pair.

Recommended prototype: give each materialized inactive campsite one distance-smoke handle at its saved fire origin. Start it once after the burnt-out object exists. Stop it when the site activates, is removed, leaves the 120-metre materialization range, or loses its object. Do not add flames or fire light, because those would make an inactive site look active.

Acceptance must prove that the smoke is visible before the five-metre prompt, does not duplicate the full camp's smoke after activation, and leaves no stale plume after removal or streaming out.

## comment 5550159211 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159211

Created: 2026-08-13T01:35:55Z; updated: 2026-08-13T01:35:55Z

Exact metadata: [source record](sources/comment-5550159211-002bf193362befcf18f6e3198bb3be54e79e5ae27f380d082e8a366ce49705e4.json).

yo thats smart asf do that. but why limit it to 120m? i want it to the max. it should lead players there. can we just have them always be on and count on the game's native culling/performance/whatever to hide em as needed?

also, if you're referring to the native vanilla campfire smoke...it's barely visible. but i've seen big tall long distance plumes across the game. i want those. i just saw some coming from here. Central union railroad.

<img width="659" height="631" alt="Image" src="https://github.com/user-attachments/assets/030813af-38b2-42c8-a5f0-71a6291c0cb8" />

Can we use those instead? 
Optimally: I want black smoke plumes for inactive campfires, white smoke for active.

## comment 5550159238 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159238

Created: 2026-08-13T04:45:20Z; updated: 2026-08-13T04:45:20Z

Exact metadata: [source record](sources/comment-5550159238-5b7b6d934eca6081928404c36256709ff1867a7b456c1dac601b9eb7d90cb765.json).

Every saved campsite now owns Rockstar's tall distant camp-smoke LOD effect. The handles stay active independent of the 120 m materialization range and rely on engine culling; inactive sites use near-black smoke and active sites use white smoke. Test both states from long range, then remove a site and confirm its plume disappears.

## comment 5550159265 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159265

Created: 2026-08-13T05:09:41Z; updated: 2026-08-13T05:09:41Z

Exact metadata: [source record](sources/comment-5550159265-84c940b1fbfe5b70288d2ce35b27ff290cfc1cba79d787529e75b79883fd32e6.json).

Returned runtime result: Story loads, but the first unpaused update crashes GameplayTweaks inside updateCampsites. The crash trace records 0xC0000005 at RDR2.exe+0x2B09400. The last completed campsite records create and color all 13 new distant-smoke handles, then the script stalls at 39 ticks in updateCampsites. This makes the all-sites smoke initialization the leading fault. Lexer-Lux/Lexeditor#272 is actionable again; no smoke behavior is accepted.

## comment 5550159291 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159291

Created: 2026-08-13T05:21:49Z; updated: 2026-08-13T05:21:49Z

Exact metadata: [source record](sources/comment-5550159291-4c33d282e300e103fadef9c63cccc586805a9c358db034640f14d951d06a1745.json).

The first-unpause crash is fixed in the installed build. I removed the Lexer-Lux/Lexeditor#272 smoke updater from runtime while leaving saved campsites and their activation logic intact. The new ASI was installed and verified after RDR2 exited. Please restart the game, enter Story, and unpause once. Distant campsite smoke is withdrawn, and this issue stays actionable until it has a safe bounded implementation.

## comment 5550159307 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159307

Created: 2026-08-13T06:33:30Z; updated: 2026-08-13T06:34:26Z

Exact metadata: [source record](sources/comment-5550159307-3b930e836b54a05676c8f056c3cbe367c97247542bc850ea661023a48b6897e1.json).

The earlier smoke attribution was wrong; the crash came from the campsite prompt survey. I restored the distant smoke with Rockstar's two-slot bound. In the live Story test, two effects stayed active for more than 13 minutes while the script passed 76,000 ticks with no exception. Please check the visual boundary from long range: inactive smoke must be black, active smoke white, and removing a selected site must remove its plume.

## comment 5550159329 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159329

Created: 2026-08-13T08:09:46Z; updated: 2026-08-13T08:09:46Z

Exact metadata: [source record](sources/comment-5550159329-ef72de5f00fb24b893a2087798499c651bce57ddad840b4cce1aefa79eb9ab93.json).

The all-camps behavior is restored. The mod now starts one missing smoke effect per second until every saved campsite has one, instead of creating all 13 in one frame. In the installed Story test, the log reached 13 live effects with none missing, remained there after 105 seconds, passed 9,548 script ticks with no stalls, and produced no ScriptHook exception. The remaining check is visual: confirm distant inactive smoke is black, active smoke is white, and deleting a campsite removes its plume.

## comment 5550159348 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159348

Created: 2026-08-20T12:38:04Z; updated: 2026-08-20T12:38:04Z

Exact metadata: [source record](sources/comment-5550159348-daa5d4376e8ceb33dd68c5427c1c595f7f93631f31f8aa9fbce29fb2b93f32cf.json).

You were right: one second was not justified by measured cost. It survived as a precaution from when smoke was incorrectly blamed for the first-unpause crash; later tracing proved the prompt survey caused that crash. The updater only checks the saved handles and starts at most one missing plume per pass. I reduced the pass to 100 ms, so 13 saved plumes should populate in about 1.3 seconds after the particle asset is ready instead of 13 seconds. The one-start bound remains, styling still happens only when activation changes, and the heartbeat now reports the exact cadence and live/missing counts. The next queued build contains this. Retest by entering Story and watching how quickly all saved plumes appear; black/white appearance and removal cleanup remain the visual checks.

## comment 5550159377 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/272#issuecomment-5550159377

Created: 2026-08-20T14:09:26Z; updated: 2026-08-20T14:09:26Z

Exact metadata: [source record](sources/comment-5550159377-8aaaba6f637ba1841067057da6004e998a088d95c6e7d0250b4ffe27ceaf1f91.json).

The one-second smoke cadence was unnecessary. Source now services one saved campsite every 100 ms, so all 15 current sites can acquire their plume in about 1.5 seconds after the particle asset is ready. Each site still owns only one engine-culled loop, inactive smoke stays black, active smoke stays white, and removal stops the plume. The focused contract rejects four cadence/lifecycle regressions. This has not been built or installed, so Lexer-Lux/Lexeditor#272 stays actionable.
