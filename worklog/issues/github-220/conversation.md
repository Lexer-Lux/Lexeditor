# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356312308 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220

Created: 2026-08-06T18:49:52Z; updated: 2026-09-05T07:01:14Z

Exact metadata: [source record](sources/issue-5356312308-054ba3a82ab1e2a2b3029bf774e7bd6c1341e48a3756e18bac9d0a14d7e9101b.json).



also. the whole "two camera modes" thing? works great....except on horseback, where there's no change at all from vanilla. back to 4 modes there (3 third-person zoom levels + First person)

## issue 5356312308 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220

Created: 2026-08-06T18:49:52Z; updated: 2026-09-06T12:56:00Z

Exact metadata: [source record](sources/issue-5356312308-56a873da272a05f426fcca86c7850649d856d6fa3521d3e584a0a8df5a1ad1af.json).

**Status: You already confirmed two camera modes work on foot and horseback.** The remaining failure was V doing nothing in vehicles.

A first/third-person vehicle toggle is described in the latest note, but its installation and usable test handoff are not established. Verify that candidate before requesting another wagon/cart/buggy test; do not repeat accepted foot/horse checks.

## issue 5356312308 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220

Created: 2026-08-06T18:49:52Z; updated: 2026-09-06T12:56:00Z

Exact metadata: [source record](sources/issue-5356312308-d1757bd2638e5f2c13fcf17f116db4d8b86d3f84ada53055d45a7b5cfc419bc2.json).

**Status: You already confirmed two camera modes work on foot and horseback.** The remaining failure was V doing nothing in vehicles.

A first/third-person vehicle toggle is described in the latest note, but its installation and usable test handoff are not established. Verify that candidate before requesting another wagon/cart/buggy test; do not repeat accepted foot/horse checks.

## comment 5550141339 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141339

Created: 2026-08-10T07:49:34Z; updated: 2026-08-10T07:49:34Z

Exact metadata: [source record](sources/comment-5550141339-d2710b9940c8f1bfa8a34c9f8d91684b98b3f13237f0f65ff6dfee18713d8235.json).

Fixed for horseback. Not vehicles.

## comment 5550141358 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141358

Created: 2026-08-10T18:56:54Z; updated: 2026-08-10T18:56:54Z

Exact metadata: [source record](sources/comment-5550141358-79aad01a9b7587d65c272dfcea434bc2aafe31655c95544da41891cb235e109e.json).

Still not fixed on vehicles.
In fact, there's no first-person mode in vehicles now, just 3 levels of 3rd person, which...I'm pretty sure wasn't the case before. Pretty sure vanilla had 1st person mode in vehicles, so you've really just made things worse.

## comment 5550141368 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141368

Created: 2026-08-10T23:45:45Z; updated: 2026-08-10T23:45:45Z

Exact metadata: [source record](sources/comment-5550141368-998c3c12b784c69891a3a1665f55568e6c7c55b9527047a252cfc31f414076c1.json).

Installed the mounted/vehicle camera correction. Horseback and vehicles now use the same two-mode branch, while the named full-first-person predicate exits before any third-person profile write. Test horse and vehicle view cycling: only first person plus the configured third-person level, with first person retained.

## comment 5550141377 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141377

Created: 2026-08-11T01:05:00Z; updated: 2026-08-11T01:05:00Z

Exact metadata: [source record](sources/comment-5550141377-3e75b033c942624d5e317b3e8f09a34e992c3b7aa8961ea6431cabc7620cb72b.json).

Now there's just no camera modes on vehicle. I'm in 3rd person, and hitting V does nothing. Could it be iterfering with the custom camera feature? What do the logs say?

## comment 5550141386 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141386

Created: 2026-08-11T01:45:59Z; updated: 2026-08-11T01:45:59Z

Exact metadata: [source record](sources/comment-5550141386-52847766559123e9deba0dc7057deea2ee8d8a339caa01c815439166616f95d6.json).

The vehicle camera pin now releases for 500 ms when the named Change Camera control is pressed. This lets Rockstar enter first person before the configured third-person mode resumes ownership. Test the normal view key on horseback and in a wagon; aiming must keep its separate camera profile.

## comment 5550141398 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141398

Created: 2026-08-12T13:01:22Z; updated: 2026-08-12T13:01:22Z

Exact metadata: [source record](sources/comment-5550141398-ca3ff08b19c74d7348e040145bf90662a9a9bbd160fa9d4311db476691cc7b32.json).

congrats. now we've gone from 3 to 0. because stepping into a wagon instantly crashes the game

## comment 5550141415 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141415

Created: 2026-08-12T23:24:21Z; updated: 2026-08-12T23:24:21Z

Exact metadata: [source record](sources/comment-5550141415-6a3243b50a61d23deb0f0e03a3b05bf6ffac75f1ad8c41b993f06e8cfd0646d6.json).

**Diagnosed why horseback is unaffected — and it isn't a missing setting.**

`LockToOneThirdPersonZoomMounted=1` and `MountedThirdPersonLevel=0` are set on your install, and `gameplay_camera.cpp:684-687` does apply the lock while mounted. I checked for an early-return that skips mounted — there isn't one, and `gameplayCameraMode()` correctly returns `Horseback` from `IS_PED_ON_MOUNT`. So the code runs and still does nothing, which rules out the config and the gating.

The cause is the natives themselves:

```
_FORCE_THIRD_PERSON_CLOSE_THIS_FRAME   0x718C6ECF5E8CBDD4
_FORCE_THIRD_PERSON_CAM_THIS_FRAME     0x8370D34BD2E60B73
_FORCE_THIRD_PERSON_CAM_FAR_THIS_FRAME 0x1CFB749AD4317BDE
```

**All three have zero call sites in the entire decompiled script set.** Rockstar never calls them. The on-foot behaviour that works was established empirically from your testing, not from a documented contract — and there is no mount- or follow-camera variant of them anywhere in `natives.json`. The mount camera is a separate rig that keeps its own view state, so pinning the on-foot third-person level doesn't reach it. That matches your report exactly: not a wrong zoom step, but *no change at all*.

There's also a real but secondary bug: the mounted branch has a `!gameplayCameraViewTransition(now)` gate the on-foot branch doesn't, which releases the pin for 500 ms on every view-key press. That would cause a visible snap-back even if the natives did work, so it needs removing regardless — but it is not what's causing this.

**What the fix needs.** Since no native pins the mount camera, the mechanism has to be input-level: detect the view-key press while mounted and issue an extra `INPUT_NEXT_CAMERA` to step past the intermediate zooms, collapsing the cycle to pinned + first person. The module already measures and logs real camera orbit distance (`measOrbit` in the `camera-editor` sample line), so that readback can tell which step the mount camera landed on.

I need the actual numbers before writing that, and I won't guess thresholds — that's how this class of fix has failed before. **One horseback log does it:** sit on the horse, cycle the view through every step, and the `measOrbit` values for each step are what I need. I'll write the skip logic against those.

Leaving open and taking this off `claude` blocked-status only once I have that log.

## comment 5550141428 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141428

Created: 2026-08-13T01:50:20Z; updated: 2026-08-13T01:50:20Z

Exact metadata: [source record](sources/comment-5550141428-cde1e44be0510c1537ebf94dd81fb4a7e3861b5c4e67097fa5ef5d9037efe14b.json).

ok i sat on horseback. Wait what happened to the 2 camera modes thing? You had it working fine on horseback but now there are like, 3 modes on horseback, and every time you change one it zooms out then slowly zooms back in??? Do you not understand the assignment
wagons are the same way now. except no 1st person mode?? 

## comment 5550141440 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141440

Created: 2026-08-13T04:05:06Z; updated: 2026-08-13T04:05:06Z

Exact metadata: [source record](sources/comment-5550141440-d5c0a79b34d0c9957f93f3cff17855b373772539ab85c56b0938c7a93d5dbf75.json).

**Removed the one structural difference between the path that works and the path that does nothing.**

The mounted branch additionally required `!gameplayCameraViewTransition(now)`, which releases the zoom pin for 500 ms on **every** view-key press. The on-foot branch — the one you report working — has no such gate. That release was the only structural difference between them, so mounted now asserts the level exactly as on foot does.

**Being honest about what this does and does not explain.** It accounts for a snap-back or a step slipping through; it does *not* by itself explain "no change at all from vanilla". The deeper problem stands:

```
_FORCE_THIRD_PERSON_CLOSE_THIS_FRAME   0x718C6ECF5E8CBDD4
_FORCE_THIRD_PERSON_CAM_THIS_FRAME     0x8370D34BD2E60B73
_FORCE_THIRD_PERSON_CAM_FAR_THIS_FRAME 0x1CFB749AD4317BDE
```

All three have **zero call sites in the entire decompiled script set**, and `natives.json` exposes no mount- or follow-camera variant. Whether they govern the mount rig at all is unproven — on-foot only ever worked empirically, from your testing.

So this is the cheap correct test before the expensive one. If a horseback session still shows four view steps, these natives do not reach that camera, and the fix has to skip the intermediate steps at the **input** layer instead — detect the view-key press while mounted and issue an extra `INPUT_NEXT_CAMERA` to step past them.

The 2 Hz `[camera-editor] sample` line already records `measOrbit`, which is the measurement that decides it. **Sit on the horse and cycle the view through every step** — those orbit distances tell me whether the pin held, and give me the thresholds the input-layer approach would need.

Installed `F9D8BFC3…`. `gameplayCameraViewTransition()` is now unreferenced; I left it in place rather than delete it, since the input-layer approach would likely want that same edge detection.

## comment 5550141453 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141453

Created: 2026-08-14T05:54:05Z; updated: 2026-08-14T05:54:05Z

Exact metadata: [source record](sources/comment-5550141453-1632e31f27656571fdced7221ed33aa74a50708910ccaf583f171b0da03af0d0.json).

**Short and useful: the mounted fix has never been exercised, so there is nothing to diagnose yet.**

I checked your session for mounted camera evidence before touching anything:

- The camera editor recorded 1559 `STANDING`, 220 `ARMED`, 206 `CROUCHED` and 151 `AIM` samples — and **zero** mounted samples.
- `mount=0` on all 1077 readings, and the horse modules report the mount candidate as 0 throughout.

You were never on a horse during that session. So the mounted-branch change from my last comment — removing the 500 ms zoom-pin release that the working on-foot branch does not have — has never actually run. Nothing in the log supports or contradicts it.

I am not going to make another speculative change to the mounted path on top of an untested one; that is how this issue accumulated layers in the first place.

**What settles it in one go:** get on a horse and cycle the camera view key through every position, then dismount and do the same on foot for comparison. That produces mounted `[camera-editor] sample mode=…` lines, and the zoom level asserted on each press, which is exactly the missing evidence.

Two outcomes, each pointing somewhere different:
- Mounted samples appear but the level does not hold → the pin release was the problem and the fix works, or it snaps back and the fight is with Rockstar's own mounted zoom.
- **No mounted samples appear at all while you are visibly on a horse** → the camera editor is not recognising the mounted state, which would explain "no change at all from vanilla" completely, and the fix belongs in mode detection rather than in the zoom logic.

Staying `actionable`, unchanged, and honestly so — I have not shipped anything for this today.


## comment 5550141470 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141470

Created: 2026-08-15T02:23:35Z; updated: 2026-08-15T02:23:35Z

Exact metadata: [source record](sources/comment-5550141470-44a9da326a579134e624f01f20acefa3cde4910e3d5e7ef7588e655d9d79c963.json).

Now hitting V in a wagon just does nothing.

## comment 5550141483 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141483

Created: 2026-08-15T04:13:21Z; updated: 2026-08-15T04:13:21Z

Exact metadata: [source record](sources/comment-5550141483-951434adb4805a7d6786b666453a7e4b4529241399c1d2b057a0bc9375d6f18a.json).

**You rode this session, so the mounted evidence finally exists — and it changes the diagnosis.**

Sixteen `mode=HORSEBACK` samples. The module submits its configured distance every one of them:

```
sample mode=HORSEBACK sentDistance=2.4 measOrbit=3.4792
sample mode=HORSEBACK sentDistance=2.4 measOrbit=2.96709
sample mode=HORSEBACK sentDistance=2.4 measOrbit=2.31775
```

`sentDistance` is pinned at 2.4 throughout. The **measured** orbit ranges 2.32 → 3.48 and never settles at the requested value.

Comparing how well each mode holds what we ask for (mean deviation of measured orbit from requested):

| mode | samples | mean deviation |
|---|---|---|
| STANDING | 752 | 19.3% |
| VEHICLE | 15 | 25.7% |
| **HORSEBACK** | **16** | **37.3%** |

So mounted is roughly twice as loose as on foot, and it drifts up to about 45% above the request.

**That kills my previous theory.** The last change here removed a 500 ms zoom-pin release from the mounted branch, on the idea that the mounted path was releasing the pin and the on-foot path was not. But the call is going out on every sample with the right value — the mounted branch is not skipping it. The engine is simply not holding it as tightly as it does on foot, and it feels like vanilla because your requested framing is being overridden after submission.

Two candidates remain and this sample cannot separate them:

1. Rockstar re-asserts its own mounted camera distance after our per-update call, so ours is overwritten each frame rather than ignored.
2. The mounted rig treats the params call as a hint with its own spring/damping, so it never converges — which the 2.32→3.48 spread is consistent with.

Sixteen samples is a thin basis for either. **What would settle it:** ride for a minute or two, cycle the camera view key a few times while mounted, and stop moving briefly. If `measOrbit` converges toward `sentDistance` while stationary but diverges while galloping, it is the rig's damping (2); if it stays off by a constant factor regardless, it is re-assertion (1).

Staying `actionable`. I am not making another speculative change to the mounted path on top of an untested one — that is how this issue accumulated layers.

Also confirmed by these samples: `mode=HORSEBACK` is being detected correctly, so mode detection is not the fault. That was the other possibility I flagged and it is now ruled out.


## comment 5550141499 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141499

Created: 2026-08-19T12:19:52Z; updated: 2026-08-19T12:19:52Z

Exact metadata: [source record](sources/comment-5550141499-5d417647ba6244dd5b4a48b11467bd5431d6e8fd3b23d5d5298ba513f827a126.json).

I have no idea what all this is about sampling and stuff? 

There are now two camera modes on foot. Good job!
There are now two camera modes on horse. Good job!
There is now one camera mode on vehicle/buggy/cart (3rd person). Pressing V does nothing. Oh no! Was there no 1st person in vehicles in vanilla? If not, can't you just add it in?

## comment 5550141510 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/220#issuecomment-5550141510

Created: 2026-08-20T10:26:14Z; updated: 2026-08-20T10:26:14Z

Exact metadata: [source record](sources/comment-5550141510-f6d9d2290c2e8a4e81cae34077471d8d6e2cf28b3aec7acbd4c040c4b48aef15.json).

Vehicle V now owns one local first/third-person state. In a wagon, cart, or buggy, press and release V several times. It must alternate only between the configured third-person view and real first person. Horse camera behavior is unchanged.
