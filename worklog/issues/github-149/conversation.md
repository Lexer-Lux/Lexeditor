# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356295621 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149

Created: 2026-08-06T02:32:54Z; updated: 2026-09-05T06:57:33Z

Exact metadata: [source record](sources/issue-5356295621-ed8f9945eb6390d744c9e3c864c7783ea5021fc53643891ff8a0518e44e5c385.json).


91.  WANTED-LEVEL DURATION AND SEARCH AREAS — How do I edit how long wanted
     levels last, how big wanted circles are, and how long it stays in that
     state afterwards where the wanted circle is gone but the cops are dark red
     dots on the map and if they see you they'll hunt for you again? I want to
     make those all last a way longer time, let me customize them in the editor.
     So you commit some big crime and you basically can't return to that area
     for ages. You commit multiple big crimes in different places in quick
     succession and every time you open up the world map you'll see these big
     places you can't return to right now.


## issue 5356295621 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149

Created: 2026-08-06T02:32:54Z; updated: 2026-09-06T12:47:30Z

Exact metadata: [source record](sources/issue-5356295621-dfcdfff431761b4ab983602af06bf65b1353b5d22a7f712f1f12731dde136e2c.json).

Expose meaningful search durations/radii and investigate persistent crime zones with working re-entry consequences.

**Status: The unsafe diagnostic crash was repaired and installed, but the requested overhaul remains research work.** Multiple drawn circles alone do not prove persistent law behavior. Prepare the remaining duration/state experiment and a concrete zone prototype before final player acceptance.

## issue 5356295621 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149

Created: 2026-08-06T02:32:54Z; updated: 2026-09-06T13:57:23Z

Exact metadata: [source record](sources/issue-5356295621-8683046cca790e500da0e32c01951b4950613cc1c6f5ff67995a92db908cf635.json).

Expose meaningful search durations/radii and investigate persistent crime zones with working re-entry consequences.

**Status: The unsafe diagnostic crash was repaired and installed, but the requested overhaul remains research work.** Multiple drawn circles alone do not prove persistent law behavior. Prepare the remaining duration/state experiment and a concrete zone prototype before final player acceptance.

## comment 5550123041 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149#issuecomment-5550123041

Created: 2026-08-06T03:57:54Z; updated: 2026-08-06T03:57:54Z

Exact metadata: [source record](sources/comment-5550123041-b63fb5ba37ceefb362ab16d91c73519640c317d42d34b0e1a634fde9a6d17b27.json).

Research result: ordinary wanted/search behavior is substantially data-editable, but long-lived multi-area exclusion needs an ASI layer. `dispatch.meta` defines Story wanted radii (60/75/90/115/150/200 by level), thresholds, spawn delays, and phase-end conditions; crime/law response data controls timeout, forgiveness, termination radii, and search reactions. The exact post-circle dark-red-law timer still needs a trace. Rockstar's active wanted state does not establish multiple remembered zones. Recommendation: expose proven vanilla fields, then persist custom crime zones (center, radius, severity, expiry) and re-arm local pressure on re-entry without fighting engine cleanup.

## comment 5550123054 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149#issuecomment-5550123054

Created: 2026-08-06T05:09:15Z; updated: 2026-08-06T05:09:15Z

Exact metadata: [source record](sources/comment-5550123054-f9f6fa6a23135449f199e613a032c4677aa2d0fae713c3eb4545b104c6b49db9.json).

so have multi-area "parole" or whatever the dark red cop things are called and multi-area wanted is doable through .asi? you checked?
okay if this ^ is doable you need a trace to make it happen then make it and i'l do it

## comment 5550123069 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149#issuecomment-5550123069

Created: 2026-08-06T07:58:37Z; updated: 2026-08-06T07:58:37Z

Exact metadata: [source record](sources/comment-5550123069-088a0df5e8aa63ef8e7ebab5179892ba19248612b21e8c3f2d73a6a524e4dc21.json).

Completed the provable editor slice: per-level wanted-circle radii, the real active-search timer `CBountyIncident.Evasion.TimeEvadingForEscape` (75 seconds vanilla), and the existing `ParoleDuration` candidate now have accurate Dispatch & Wanted controls/help. The live editor server has been restarted and the 75-second row verified through its API. Lexer-Lux/Lexeditor#149 remains actionable because `ParoleDuration` still needs an in-game A/B to establish its exact dark-red-lawman behavior/unit, and vanilla data does not prove multiple simultaneous persistent crime circles.

## comment 5550123083 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149#issuecomment-5550123083

Created: 2026-08-06T13:32:26Z; updated: 2026-08-06T13:32:26Z

Exact metadata: [source record](sources/comment-5550123083-52dbbd2884d9f750c690e1261ddebd7ab408bb454fd70be9f33f959fa9031493.json).

so then how do i prove multiple simultaneous crime circles? am i supposed to just go out and test it myself? 

## comment 5550123104 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149#issuecomment-5550123104

Created: 2026-08-09T07:37:07Z; updated: 2026-08-09T07:37:07Z

Exact metadata: [source record](sources/comment-5550123104-5cce35fa516f9b3b3031f9984719f444527e2ca11d9ead5ed4a3eb5dc6323981.json).

Second-pass research now proves multiple displayed circles are feasible, but not yet the full re-entry law response.

`dispatch.meta` defines wanted radii 60/75/90/115/150/200. `short_update.c:27704-27727` consumes `GET_WANTED_LEVEL_RADIUS`, stores one incident center/radius per jurisdiction in `Global_40.f_358[state]`, but owns only one displayed handle `Global_1934266.f_151`, moved/rescaled for the current jurisdiction. Vanilla therefore does not display simultaneous historic circles.

An ASI can own several independent circles: `BLIP_ADD_FOR_RADIUS` (`0x45F13B7E0A15C880`) returns independent handles, Story scripts retain radius-blip arrays, and `BLIP_STYLE_WANTED_RADIUS` is authored for `COLOR_WANTED`, alpha 0.4, and PauseMap/ALWAYS. Multiple persistent zones require an ASI sidecar containing center, radius, severity, and expiry; Rockstar’s per-jurisdiction slots only preserve one recent zone per state, and their restart lifetime is unproven. Re-entry pressure is plausible through `LAW::_REPORT_CRIME` (`0xF60386770878A98F`, used by `law_arrest.c:476`) but must demonstrate a new visible law incident before being called working.

Duration corrections: `TimeEvadingForEscape=75.0` is the strongest named active-evasion candidate, not statically proven as the consumer. `HiddenEvasionTimes=0` does not prove unused. `ParoleDuration=9000` has no Story-script reference, so its unit/consumer and dark-red-lawman meaning remain unknown. `short_update.c` state 7 shows `LAW_UI_LAW_SEARCHING`; state 8 sets cooldown flags and waits hard-coded 10000/35000 ms while calling unresolved PLAYER natives. That is likely the reported post-circle phase, but exact ownership is not proven.

Current F8 trace cannot settle it: it omits the script presentation state/cooldown flags, calls state natives every frame despite a later 250 ms output throttle, and installed `Verbose=0` produced BEGIN with no samples. A valid diagnostic must sample no faster than 250 ms, log presentation transitions at INFO, preserve previous evidence, emit idle heartbeats, and A/B `ParoleDuration=9000` against a materially different value. No manual F8 timing should be needed once script state is captured.

No implementation or label change was made. Custom zone controls belong in LEXEDITOR only after the ASI mechanism is proven.

## comment 5550123114 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/149#issuecomment-5550123114

Created: 2026-08-15T21:02:58Z; updated: 2026-08-15T21:02:58Z

Exact metadata: [source record](sources/comment-5550123114-ce4315e661f6dabdbca07f9ace8e8a71e1e5feb6444f157d8e6825f915679744.json).

The Windows crash dump identified the cause: the wanted-state trace's registered-crime query wrote past its local C++ record and tripped stack protection. I removed that query and its caller-owned buffer. The trace keeps the safe wanted, law, witness, HUD-crime, and nearby-law observations and now records that registered crimes are not sampled. The repaired development ASI is installed. Repeat one normal crime, escape, and post-search tail; confirm the wanted trace continues after its first sample and the game does not freeze or crash.
