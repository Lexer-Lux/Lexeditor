# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356310350 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212

Created: 2026-08-06T07:43:05Z; updated: 2026-09-05T07:00:50Z

Exact metadata: [source record](sources/issue-5356310350-fab8e50cdb3d05696e09fdbc32a99bfc00da75a620b0950f64d5802a012571a4.json).

in .ini. misc. i have to rotate my scroll wheel like a million fucking times every time i open it i hate ts bruh

## issue 5356310350 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212

Created: 2026-08-06T07:43:05Z; updated: 2026-09-06T12:55:54Z

Exact metadata: [source record](sources/issue-5356310350-8d62f42f956c0328e88da890e87bc631945ab892bfc64b00a1d523e111ebc1e9.json).

**Status: The tested input-queue approach failed and was removed.** It added delayed equal-sized zoom steps, stalls and beeps instead of increasing zoom strength. No supported script setter for that strength is established.

This is separate from the already accepted map-centering behavior. No zoom-speed setting or ready test remains.

## comment 5550139286 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139286

Created: 2026-08-06T08:43:35Z; updated: 2026-08-06T08:43:35Z

Exact metadata: [source record](sources/comment-5550139286-c3e491def2759a36a8f443cc881d77981a55dfea40b1ff98342a18382d765c01.json).

Implemented `[Misc] MapZoomSpeedMultiplier` (1.0 vanilla through 10.0, default 4.0), including fractional pulse accumulation and queue reset when MAP closes. Included in queued superset ASI `E85AA9E20E284EECB7E580C6C767724B38FF335917CBF4447956E4E992D6DEDA`; remains `actionable` until installed, then moves to `test me`.

## comment 5550139298 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139298

Created: 2026-08-06T11:52:37Z; updated: 2026-08-06T11:52:37Z

Exact metadata: [source record](sources/comment-5550139298-69073df025641b83aebc08142bd73bf1d0853eb5b8d198921fd08ee0c70532e8.json).

i tried both 999 and 1e-4 and i see no difference. do i need to restart to apply or somethinG?

## comment 5550139316 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139316

Created: 2026-08-06T12:08:02Z; updated: 2026-08-06T12:08:02Z

Exact metadata: [source record](sources/comment-5550139316-776c3002015462bef9bc2540b3a51ff8fab9a84eada202734fe4de98c298eaf1.json).

The multiplier itself hot-reloads once the implementation is loaded, but the ASI you tested did not contain the corrected implementation, so changing 999 or 1e-4 could not affect it. The new ASI is installed on disk for the next full restart (D4189A...1AC8); after that, [Misc] MapZoomSpeedMultiplier hot-reloads in about one second and clamps to 1.0-10.0. Moved to 	est me.

## comment 5550139325 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139325

Created: 2026-08-06T12:42:30Z; updated: 2026-08-06T12:42:30Z

Exact metadata: [source record](sources/comment-5550139325-f73b2e26c060a4e99bb9fa31227615065d43569f074656a6172c34927e0b07d2.json).

still no difference.

## comment 5550139337 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139337

Created: 2026-08-06T13:27:13Z; updated: 2026-08-06T13:27:13Z

Exact metadata: [source record](sources/comment-5550139337-0f37a2079e7cbaf29481e1d378e8dbd32620a5cc566758e55b30c58a07398a7f.json).

The installed control-value injection was disproven by both mouse and gamepad tests, even with the configured 999 value clamped to 10x. It has been replaced and installed in development build F1A98C615AB3D0B4D1DB0BD4520144D789F51CF5F84C495C2E595D5452CF3B96. The replacement detects wheel or controller RS-Y input and adds bounded foreground-only Windows wheel events instead of ignored PAD values. Test 1.0 versus 4.0 and 10.0 on the pause map with both devices. Direction must remain correct and 1.0 must be vanilla. If unchanged, attach GameplayTweaks.map-zoom.log; its sent= value distinguishes delivery failure from MAP rejection.

## comment 5550139348 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139348

Created: 2026-08-06T13:42:38Z; updated: 2026-08-06T13:42:38Z

Exact metadata: [source record](sources/comment-5550139348-754a66e897dd210039458e3a0bb0ff8dc691f6dcae9defa85c346815f32193a3.json).

Still not seeing any change.

## comment 5550139355 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139355

Created: 2026-08-06T14:42:32Z; updated: 2026-08-06T14:42:32Z

Exact metadata: [source record](sources/comment-5550139355-d50722ed9a1e72f778d4ff22536c2dd8b1ceb077cf6e6e876f0892a62c40fb7a.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Test MapZoomSpeedMultiplier at 1, 4, and 999 with both mouse wheel and controller right-stick in both directions. Attach GameplayTweaks.map-zoom.log; 999 should hit the bounded maximum without recursive input.

## comment 5550139369 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139369

Created: 2026-08-06T17:07:38Z; updated: 2026-08-06T17:07:38Z

Exact metadata: [source record](sources/comment-5550139369-5d9eb214125fd4add8f39f01f76c32a778b4d89fce0d6a064aea86b4b643ff6c.json).

no change.

## comment 5550139380 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139380

Created: 2026-08-06T18:52:58Z; updated: 2026-08-06T18:52:58Z

Exact metadata: [source record](sources/comment-5550139380-070a1e9a5ffad62075ca8eb2020b610ee2d409853f88f71ddb5a0998c8ef54ab.json).

Rewritten after establishing why four attempts did nothing.

Pause-map zoom is **not script-reachable**. Across all 1639 decompiled scripts, `map_app_event_handler.c` has zero `zoom` matches and zero `PAD::` natives; `pause_menu.c` (27466 lines) likewise. The only zoom native used anywhere is `MAP::SET_RADAR_ZOOM` (minimap only). Attempts 1-2 wrote the script-side control-value override buffer, which the native MAP UIApp never reads — that alone explains "no effect on mouse and gamepad".

Attempts 3-4 never delivered anything. `GameplayTweaks.map-zoom.log` holds 28 lines across ~28 launches, several at `applied=999`, and every line is a `config` line — not one `sent=` burst. Delivery was never exercised, so "MAP rejects synthetic input" was never actually tested.

Corroboration: `updatePauseMapRecenter` (`modules/collectibles_map.cpp:823`) gates on the same `UIAPP_ACTIVE("MAP")`, and Lexer-Lux/Lexeditor#114 fails identically — map opens at player location (ungated branch) but Recenter never appears and its log does not exist (gated branch). Two unrelated features fail the moment the pause map opens.

Detection moved off the game control layer: `WH_MOUSE_LL` on a dedicated pumped thread, RS-Y via `XInputGetState`, structural recursion guard (`LLMHF_INJECTED`), delivery on the pump loop rather than in the hook callback, gate widened to MAP UIApp or `IS_PAUSE_MENU_ACTIVE` or `_UI_IS_SINGLEPLAYER_PAUSE_MENU_ACTIVE` published as a 1500 ms deadline. Two independent heartbeats added.

Built, SHA-256 `D7A3A305D74AA519F008336C008451D5CD5348FE3894BBC34E044000F0B0B479`, install queued behind the running game. Staying `actionable` until it lands.

**This build is instrumentation, not a fifth guess.** Open the map ~20s at 999, scroll both ways, push RS up/down, attach `GameplayTweaks.map-zoom.log`:

| Log signature | Meaning |
|---|---|
| `hb hook` continues, `hb script` stops | script thread suspended by pause menu -> Lexer-Lux/Lexeditor#212 unfeasible from an ASI, relabel; Lexer-Lux/Lexeditor#114 shares the cause |
| `hb script` continues with `mapApp=0` | MAP hash is the wrong gate; the line names the right one |
| `mapApp=1`, no `wheel` line on scroll | hook blind to the device (raw/exclusive input) |
| `wheel ... sent=N` and zoom still vanilla | input delivered, MAP ignores it — mechanism dead |

The zoom *rate* is settled as not script-visible, permanently. Duplicating real input is the only remaining avenue; if the log shows the heartbeat gap, the right call is unfeasible rather than a sixth mechanism.

## comment 5550139406 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139406

Created: 2026-08-06T18:59:39Z; updated: 2026-08-06T18:59:39Z

Exact metadata: [source record](sources/comment-5550139406-d98885b79d601c8e8b6189706445d15ebe9e7b4022f23e0b518c46dff189deae.json).

Install verified. `GameplayTweaks.asi` in the game root hashes SHA-256 `D7A3A305D74AA519F008336C008451D5CD5348FE3894BBC34E044000F0B0B479`, matching the build. Moved to `test me`.

## comment 5550139414 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139414

Created: 2026-08-06T19:33:06Z; updated: 2026-08-06T19:33:06Z

Exact metadata: [source record](sources/comment-5550139414-a6d09e5122f722d5da455f267800a43ead73b391aa28a7d0e57bfcc2a7a20965.json).

at 999 or 10 i hear that beep you get when your computer freezes when you open the map and scroll out. then it scrolls way out. then...i can scroll in and out normally. no beep, normal zoom speed.
at 5 it acctually lags, i get way more beeps, it lasts longer.
it's like you coded this in the weirdest way ever.

## comment 5550139429 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139429

Created: 2026-08-09T07:09:21Z; updated: 2026-08-09T07:09:21Z

Exact metadata: [source record](sources/comment-5550139429-8464a395eef02827549647217ad61fc752dfb281c36a02e560c232abd1d1184a.json).

Your last runtime report already proved the mechanism was feasible and identified both defects:

- The beep/stall came from flooding up to 30 separate SendInput wheel events in one call.
- The return to vanilla speed came from the map gate expiring after 1500 ms while the ScriptHook thread was suspended by the open map.

I replaced the burst with a capped queue delivered one extra notch every 20 ms, and replaced the deadline with a pause-session latch that stays open while the map suspends scripts and clears after scripts resume on close. Direction changes discard opposite queued momentum. The unified [map-zoom] heartbeat reports latched state, queue depth, delivered total, and failures.

The static verifier now rejects bulk bursts and requires the latch/paced delivery. Development build B6AB21D942A05E930882286F5D3ADECEC10D52D1D77A178244C3B98A3360B9F1 passes, but I have not installed it over the recon-crash candidate currently awaiting its runtime result. Lexer-Lux/Lexeditor#212 remains actionable; no label was changed.

## comment 5550139448 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139448

Created: 2026-08-09T07:19:08Z; updated: 2026-08-09T07:19:08Z

Exact metadata: [source record](sources/comment-5550139448-531172d2d0afe80334859bca5bb40510560148f22acb9bb233e5317819913c36.json).

The session latch and paced one-notch delivery are now installed and hash-verified in development ASI BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5. Test multipliers 1, 5, and 999 in one map session: acceleration should persist until close, reverse immediately, and produce no Windows beep or stall. Moved from actionable to test me and read back OPEN with only test me.

## comment 5550139461 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139461

Created: 2026-08-09T09:02:30Z; updated: 2026-08-09T09:02:30Z

Exact metadata: [source record](sources/comment-5550139461-00b1c80c12e968175bcde6f8f4d015609a38fccd77b7bdafd08da05a5d9dcbd9.json).

absolutely bizarre.
0.01 = feels like vanilla? could be wrong.
1 = feels like 0.01
10 = every time i scroll my wheel a notch there's a moment's pause then it's like it has 50 equally-sized zoom out steps queued? like that's the only thing this multiplier is doing -- not actually increasing the STRENGTH of the zoom but just artificially queueing a bunch of zoom in/out inputs? sometimes they go all in evenly spaced intervals. often there's big hitches because there's so much lag. oftentimes they don't all even come out because the lag is so bad, so every move of the scroll wheel can have radically different amounts of zoom

## comment 5550139471 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139471

Created: 2026-08-09T11:07:22Z; updated: 2026-08-09T11:07:22Z

Exact metadata: [source record](sources/comment-5550139471-70acdece6eb86ad15807eb17f085664368f40110d43de3d2afc340671838f61f.json).

Runtime testing proved the hook did not change zoom-step strength: it queued more equal-sized steps and caused delayed motion, stalls, and beeps. MAP exposes no script zoom-strength setter. The synthetic hook, SendInput queue, INI/editor setting, and dispatcher path are removed in installed build 696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53.

## comment 5550139483 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/212#issuecomment-5550139483

Created: 2026-08-10T10:20:50Z; updated: 2026-08-10T10:20:50Z

Exact metadata: [source record](sources/comment-5550139483-2280be8d70eeca6c86ba237263de86287b01651718513d6f050c4c327f8276ff.json).

Tracker split confirmed: adjustable map zoom speed is separate from Lexer-Lux/Lexeditor#114. Runtime proved that the available mechanism only queues equal-sized zoom inputs and causes lag rather than changing zoom-step strength; MAP exposes no script-reachable zoom-strength setter. Keeping Lexer-Lux/Lexeditor#212 open with only the unfeasible label.
