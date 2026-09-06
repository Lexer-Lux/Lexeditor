# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356325322 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269

Created: 2026-08-11T04:18:50Z; updated: 2026-09-05T07:03:55Z

Exact metadata: [source record](sources/issue-5356325322-9d0eef50c9d98fdb32f933bca5780797f7ec3f254fdf3f81a55ebcbaa80fbea7.json).

Stand: camera mode is standing.
Unholster gun: camera mode is standing. Debug text indicates same horizontal and distance. Yet...no. Unholestering a gun clearly moves the camera a bit. Is this some kind of other camera mode that wasn't accounted for?

## issue 5356325322 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269

Created: 2026-08-11T04:18:50Z; updated: 2026-09-06T12:56:58Z

Exact metadata: [source record](sources/issue-5356325322-375a30b82487d7204426d9191e6e7f229e01c5eccd399f7e33120916c27a37ab.json).

Drawing a weapon should not introduce an unexplained camera movement or mismatched transition.

**Status: The latest automatic recorder is source-only; the final curve repair is unfinished.** It now preserves a true pre-change frame and needs no Numpad 9 input. Install it before requesting one normal transition recording; do not repeat the old recorder that changed the camera itself.

## issue 5356325322 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269

Created: 2026-08-11T04:18:50Z; updated: 2026-09-06T12:56:58Z

Exact metadata: [source record](sources/issue-5356325322-efd0ac74a185a3f44815d65e0ea9163ac56822ec568c515933439b41912c81ef.json).

Drawing a weapon should not introduce an unexplained camera movement or mismatched transition.

**Status: The latest automatic recorder is source-only; the final curve repair is unfinished.** It now preserves a true pre-change frame and needs no Numpad 9 input. Install it before requesting one normal transition recording; do not repeat the old recorder that changed the camera itself.

## comment 5550157354 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157354

Created: 2026-08-11T09:32:40Z; updated: 2026-08-11T09:32:40Z

Exact metadata: [source record](sources/comment-5550157354-4cccf37839906d90727045b08cad106e1e567dbc13ce0bc6cad7c404afa1fa0b.json).

Camera selection now distinguishes ARMED and CROUCHED ARMED from the holstered standing/crouched profiles through Rockstar's current-weapon-holstered readback. Draw and holster a weapon in both stances and confirm the camera changes once without a position jump.

## comment 5550157400 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157400

Created: 2026-08-13T01:52:24Z; updated: 2026-08-13T01:52:24Z

Exact metadata: [source record](sources/comment-5550157400-55f7f8739d35cdc43310d50ce3d54020a3154e0b673b75ac54f76f7c219970ea.json).

Going from armed to standing or vice versa has this weird hitch. like it jumps horizontally then moves smoothly vertically? how many times do i have to say that camera transitions should be smooth. all done through the same code. the same way. DRY.

## comment 5550157437 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157437

Created: 2026-08-14T00:55:15Z; updated: 2026-08-14T00:55:15Z

Exact metadata: [source record](sources/comment-5550157437-7bbc384022ba8201ffda7f0bc208ab20002be996a97a90fdd62ae37241a93c93.json).

**Found the asymmetry you described, and it is exactly what you said it was.**

You said it jumps horizontally and then moves smoothly. That is precisely what the code did:

- **Distance** was passed to the camera native along with `BlendSpeed` as its first argument, so the engine blended it.
- **Horizontal** was passed as `profile.horizontal` — the raw target value. The moment the mode changed from armed to standing or back, the submitted lateral offset **stepped** from one profile's number to the other's in a single frame.

One value blended, one teleported, through the same call. Nothing was smoothing the horizontal at all, so no amount of tuning `BlendSpeed` was ever going to help it — that argument only reaches the part that already worked.

The horizontal is now eased toward its target instead of stepped. Specifics, because they matter for how it will feel:

- Time-based, not per-frame, so the transition takes the same real time whether you are at 60 or 120 fps.
- Roughly 250 ms for a full-scale change, which is in the same range as the distance blend rather than a slow drift.
- The step is clamped, so a long frame or an alt-tab cannot skip the whole distance and reintroduce the jump.
- It only affects frames where the target actually changed. Once it arrives the value is exact, so **no steady-state framing is altered** — every profile number you have tuned still means exactly what it meant.

Test: draw a weapon and holster it a few times while standing still, and watch the horizontal offset move rather than snap. Then do it while crouched and while aiming, since those are separate profiles and each transition now eases.

Related, from today's work on Lexer-Lux/Lexeditor#267: a bounded one-second probe now opens right after a shoulder flip, during which lateral is handed to the engine. If you see a brief lateral shift immediately after pressing X, that is the probe, not this easing.

Not runtime-verified — no frame has rendered it. But the step was real and is gone.


## comment 5550157473 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157473

Created: 2026-08-19T12:27:50Z; updated: 2026-08-19T12:27:50Z

Exact metadata: [source record](sources/comment-5550157473-0752ef12d3d88012c13cc61fd1f36f5b3c58411812e3127d490eed59189fda2f.json).

Okay, now the zooming pattern is like..this zig-zag. When I draw/holster a weapon, the camera starts (smoothly), going out, then starts smoothly going to the side while going out, then stops going to the side and smoothly finished going out. I want ALL the X/Y/Z/FOV/whatever changes to begin and end at the same time with the same tweening curve.

## comment 5550157505 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157505

Created: 2026-08-20T05:42:27Z; updated: 2026-08-20T05:42:27Z

Exact metadata: [source record](sources/comment-5550157505-5e05e1331cb40bcf51156b990b7c639cef1b0b15f5ba2759dbd506969c7fdcd8.json).

**Both halves of this issue are now answered from the log, and the second one has a concrete cause.**

**The original question — "is this some kind of other camera mode that wasn't accounted for?" — yes.** There is a distinct `ARMED` mode with its own framing, separate from `STANDING`:

```
mode transition from=STANDING to=ARMED  fromDistance=4.95 toDistance=2.1
```

Drawing a weapon moves the camera because it changes mode, and the two profiles differ by nearly three metres of distance. It is accounted for now and appears in the telemetry.

**The zig-zag has a specific mechanism: the dwell is shorter than the transition.**

```
mode transition from=STANDING to=AIM   dwellMs=100
mode transition from=AIM to=ARMED      dwellMs=100
```

The mode dwell is **100 ms**; `TransitionMs` is **250 ms**. A second mode change is therefore admitted 100 ms into a 250 ms ramp. Drawing a weapon walks a CHAIN of modes — `STANDING -> ARMED -> AIM` — and each link re-aims the ramp while it is still moving. Measured across the session: **four of the 26 ramps had a second ramp start within three seconds**, e.g.

```
1886312 AIM->AIM      then +500 ms   AIM->STANDING
2547921 ARMED->ARMED  then +1500 ms  ARMED->STANDING
```

Both axes were already sharing one clock — that part of the earlier unification works, and the log confirms it (at `txProgress=0.5`, `sentHorizontal` and `sentDistance` are each exactly half-way). What changed mid-move was the TARGET, so the camera visibly changed direction part-way through: out, then sideways-while-out, then out again. Exactly as described.

**Fix: a mode change now waits for the in-flight ramp to finish.** One draw or holster produces one move that begins and ends together. The dwell still applies on top, so a change can only ever be delayed, never dropped, and `modeDeferrals=` on the heartbeat counts how often a change was held back.

Contract updated and mutation-tested: removing the ramp gate fails immediately.

Installed `8BA97C22E06C2D3B045F6068616E917BDF6409732EF2B75AED42738DE5D7FF12`, hash verified.

What to watch: draw and holster repeatedly. The movement should be a single smooth change with no direction reversal partway. If it still zig-zags, `modeDeferrals=` will say whether the second transition was actually held — if that number stays at zero while the zig-zag persists, the extra motion is coming from something other than our mode chain, and that is a different defect.


## comment 5550157552 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157552

Created: 2026-08-20T09:26:22Z; updated: 2026-08-20T09:27:37Z

Exact metadata: [source record](sources/comment-5550157552-6029f1ecf4bd2032310c4c2bc03917f5348472958bc0808b3f18decfd09e3cca.json).

Returned test: STANDING in LOW framing -> draw weapon still renders as two movements. The camera first moves toward the ped, then rises. This fails the requirement that every camera-state change start and stop together on one curve.

The previous “one move” claim was too broad. The module gives only horizontal offset and distance to its 250 ms smoothstep. LOW/NORMAL uses a separate Boolean camera native with Rockstar’s own interpolation, and NORMAL is currently sent only once. FOV is not part of either path. Starting those calls on the same frame does not make them one transition.

The Lexer-Lux/Lexeditor#269 verifier missed this. It checks that a second profile cannot interrupt the horizontal/distance ramp; it never checks rendered vertical motion or the LOW/NORMAL path.

Vanilla must first be measured with the override disabled: record rendered lateral position, orbit distance, vertical position, rotation, and FOV through the same draw/holster change. If FOV stays fixed, Rockstar's observed LOW/NORMAL vertical response can be the master progress curve and the module can drive horizontal offset and distance from that same progress instead of using an unrelated hard-coded 250 ms smoothstep. The current build never performed that measurement. If FOV or another uncontrolled value also changes on a different curve, the gameplay-camera setter cannot synchronize it; exact full-transform control then needs either a proved current-build internal control or a scripted camera seeded from the vanilla pose. A scripted camera also takes ownership of collision, aiming, shoulder changes, and mounted behavior, so it is the larger fallback, not the first assumption.

Acceptance: STANDING LOW -> ARMED/NORMAL and the reverse must render one monotonic movement. Lateral, distance, vertical framing, and any changed FOV must begin together, follow one curve, and settle together.

## comment 5550157610 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157610

Created: 2026-08-20T10:28:47Z; updated: 2026-08-20T10:28:47Z

Exact metadata: [source record](sources/comment-5550157610-c167047efb479c936ff423b64d6c2cdb988fa94a63bf2547315e41475c8bae7a.json).

I did not guess a second camera curve. The installed build adds a bounded vanilla capture for the missing evidence. Standing in third person without aiming, press Numpad9, wait for the ready line, then draw or holster once. It records lateral, distance, vertical, rotation, and gameplay/rendered FOV through the real vanilla move. This is measurement for the synchronization repair, not a claim that the two-stage movement is fixed.

## comment 5550157653 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157653

Created: 2026-08-20T12:26:06Z; updated: 2026-08-20T12:26:06Z

Exact metadata: [source record](sources/comment-5550157653-25724e712f736ab0b2b1f11af10453ed7c5925cc94d8bc71c154b326915b6325.json).

Your Numpad 9 observation was correct. The recorder itself was changing the test: every arm forced NORMAL once and then stopped all of the module's camera writes while it waited and recorded. The installed log also shows the key path re-arming several times within one second. I removed Numpad 9 from this job completely. The next build records automatically whenever the raw profile, applied profile, LOW/NORMAL value, or weapon state changes. It records after the normal camera updates and performs no camera or input write, so it cannot add or interrupt movement. Reproduce the bad transition with whichever profile values expose it; there is no key to press. When your normal test session ends, the queued build will install. On the following session, reproduce once and stop the game when convenient. The log will contain the full transition. The final plan is still to use the measured LOW/NORMAL response as the master schedule for horizontal and distance, so every controllable value starts, follows the same curve, and settles with it.

## comment 5550157684 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/269#issuecomment-5550157684

Created: 2026-08-20T14:20:37Z; updated: 2026-08-20T14:20:37Z

Exact metadata: [source record](sources/comment-5550157684-1ef359f13533e2a58f0c680ff1e0df9e4f8c846dc04169e1c8cc5de3fb011661.json).

The automatic recorder no longer needs Numpad9 and still performs no camera or input writes. One measurement gap remained: it first sampled after the state edge, so it had no true pre-change rendered position, rotation, FOV, or look baseline. It now preserves the prior eligible rendered frame and emits that baseline before the transition samples. This gives the later curve repair a real starting point instead of a guessed one. Source and focused camera checks pass, but this change is not built or installed; the final shared-curve repair still waits for the automatic runtime sample.
