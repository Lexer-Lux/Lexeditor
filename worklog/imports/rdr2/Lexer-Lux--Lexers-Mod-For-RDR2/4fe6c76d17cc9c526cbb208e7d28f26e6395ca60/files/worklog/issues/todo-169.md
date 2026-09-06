# Worklog: Todo 169

## #169 climbing — the geometry was wrong at the root 2026-08-05 (second pass)

Lexer, correctly and for the Nth time: "get the position his hands and feet
should be at, move and rotate him to that position." Everything before this pass
fitted a plane and then placed him against it with a scalar standoff while
leaving ORIENTATION as an INI toggle that defaulted OFF. Two independent bugs,
both of which vanish on a vertical wall and both of which bury him on a slope.

1. ROOT PLACEMENT WALKED DOWN THE WORLD, NOT THE FACE.
   `anchor = contact.point - (0,0,contactHeight) + normal*offset`
   The contact sits ON the surface at ~chest height; the drop to the feet was a
   world-space (0,0,-h). Dropping straight down from a point on a sloped face
   travels INTO it. Penetration = h * normal.z. At Lexer's 45 degrees that is
   1.0 * 0.707 = 0.71 m of burial against a 0.30 standoff, so hips and legs sit
   ~0.4 m inside solid rock before any animation plays. normal.z = 0 on a
   vertical wall, where straight-down IS along the face and the error is exactly
   zero — which is why every flat-wall test passed and every slope failed, and
   why "improve the contact fit" (centroid -> most-protruding point, hand
   clearance correction) could never touch it. Now `climbRootFromContact()`
   walks down `climbSurfaceUp(normal)` instead of world down.

2. ORIENTATION WAS OPTIONAL. `AlignPitchToSurface` defaulted to FALSE, so by
   default he stood bolt upright against every incline with only heading
   tracking it. Now defaults true in both the declaration and `readB`, and in
   the INI. The reason it was made optional is real - SET_ENTITY_ROTATION every
   frame re-poses the ped and resets the clip to frame 0 (the old A-pose) - so
   the fix is not to skip the rotation but to stop issuing it sixty times a
   second: `appliedPitch`/`appliedHeading` latches re-issue it only when the
   orientation actually moved >0.75 deg. On a smoothed steady face that is a call
   every few seconds. PitchSign remains the escape hatch for the engine's sign
   convention, which still cannot be confirmed without running.

3. THE MANTLE INHERITED #2. ToppingOut arced him over the lip STILL LEANED at
   the face's angle, so he crossed the edge tilted and landed on flat ground at
   a slope's attitude. `g_climbTopOutPitch` captures the lean at entry and it is
   unwound across the arc under the same >0.75 deg re-issue rule.

4. SIDEWAYS, THE ACTUAL ROOT CAUSE — and the previous pass's fix was necessary
   but insufficient. Last pass corrected the PREDICATE to query the dict a clip
   was issued from. The corrected trace then said, in Lexer's own session on
   build 07:47:14:
     wantClip=base_right_hand_up
     animDict=script_story@fus1@ig@ig_1_cliffsidetraverse animPlaying=0 gain=0
   The ISSUE SITE was already wrong: `dict` was chosen from the MOTION
   (`side ? kClimbSideDict : kClimbAnimDict`) while `wantClip` is chosen from
   CONFIGURATION. With UseStoryLateralClip=0 the sideways clip is a grip out of
   mech_ladders@base, so TASK_PLAY_ANIM got a clip name absent from the
   dictionary it was pointed at. Nothing played -> gate saw no anim -> speed 0.
   `dict` is now derived FROM `wantClip`, the one thing that cannot disagree
   with itself. NOTE FOR NEXT TIME: fixing the observer before the observed is
   what made this visible - the trace had been printing animPlaying=0 phase=0
   for every lateral frame for as long as lateral clips lived elsewhere.

5. THE HITCH ON RELEASE. Letting go sent Up/Down into a `Settling` state that
   played `climb_up_settle_*_hand` - an authored clip whose entire content is
   one more reach upward - AND flipped `g_climbIdleLeftHand`, so it blended into
   the OPPOSITE grip. Two pieces of unrequested motion arriving after the player
   stopped asking for any; exactly the "one additional little move up with his
   hand". Release now goes straight to the grip already held.

BUILD BLOCKER, NOT OURS: script.cpp:5045 (plant-model loader, #113 work) had a
corrupted character constant - `line.back() == '<literal newline>'` - which is
C2001/C2137 and blocked the whole build. Restored to '
'. Beware: a naive
text-tool replacement here writes a raw 0x0D back into the quotes and still
looks right in a terminal; it must be written as the two-byte escape. Verified
with `od -c`.

Concurrency: another agent is editing script.cpp in the same tree (an Edit hit
EPERM mid-session and the INI was restructured underneath us). Nothing here is
committed for that reason.

NOT VERIFIED IN-GAME. Built Aug 5 18:04, installed.


## #169 free climbing — seven-defect pass from trace evidence 2026-08-05

BEFORE ANY DIAGNOSIS: two of the seven were never in the build under test. The
installed .asi was stamped 07:06; the climbing log's last write was 06:58 and its
last build banner `Aug 5 2026 06:19:13`. `git show HEAD:...script.cpp` vs the
working tree confirms `TopOutClearanceMeters` / the `#169(f)` arc-doubling and the
`#169(e)` REVERSE-MANTLE reverse probe existed ONLY in the uncommitted tree,
compiled after the session ended. Lexer's (e) summit clipping and (g) reverse
mantling were therefore untested, not unchanged. Letter schemes have drifted
between rounds — the in-code `#169(x)` comments use the OLD scheme and no longer
line up with Lexer's current a–g. Do not assume they match.

(f) SIDEWAYS MOVEMENT WAS MULTIPLIED BY ZERO. `motionAnimPlaying` gated speed on
`IS_ENTITY_PLAYING_ANIM`, choosing the dict from the MOTION:
`lateralMotion ? kClimbSideDict : kClimbAnimDict`. But with `UseStoryLateralClip=0`
(default since the story clip was rejected as "dancing") the lateral clip is
`kClimbIdleLeft/Right` out of `mech_ladders@base`, and when the narrow-ledge probe
succeeds it is `g_climbLedgeClip` out of `kClimbLedgeDict`. Neither is
`kClimbSideDict`, so the predicate was structurally unsatisfiable, `motionGain`
stayed 0.0, and `speed = moveSpeed * 0.0`. Clip SELECTION was correct throughout,
which is why the logs looked healthy. Fix: `g_climbAnimDictInUse` records the dict
at every `TASK_PLAY_ANIM` site and the predicate queries that.

(a) SLIDE→CLIMB: DETECTION FINE, PROBES BLIND. Log counts: `nativeSlide=1` on 262
frames, `grounded -> grabbing` on 3. `grep 'nativeSlide=1' | grep -c 'fresh=0'` =
228. Entry requires `contactFresh`, and unattached probes are horizontal
(`climbScanDirection` returns a z=0 vector from facing or camera yaw, alternating).
Sliding scree he faces downhill, so all six rays leave over open air; the slope is
beneath and behind. Fix: `g_climbScanSlideValid` / `g_climbScanSlide` override set
only around `beginClimbProbes` (so `intended`/`forwardSpeed`, computed earlier for
the slip test, stay uncontaminated) = normalized(-horizontal velocity) tilted ~40
below horizontal, reach raised to max(GrabDistance, 2.20) since a downward ray must
cross the body's own height first.

(b) MANTLE EJECTION. Post-top-out trace at 521572328+: velocityZ +1.51573, then
airborne=1 -0.972269, then -2.17985. Solver ejection from interpenetration, then a
fall — a pop-and-reland on every climb. Cause: `releaseClimbPhysics(ped, false)`.
`snapToGround=false` exists so a LEAP keeps its arc; the grounded branch (stand
upright, back off along the normal, GROUND_Z, zero velocity) is precisely what a
mantle needs. Now passes true.

(d) MOVEMENT-BEFORE-ANIM IS AN ORDERING BUG. `motionGain` is computed ~line 7975;
the state machine that derives `requested`, updates `g_climbMotion` and issues the
clip runs ~line 8040, at the BOTTOM. On the first frame of input the gain reads the
PREVIOUS clip — the idle grip, playing for seconds — so `motionAnimPlaying` is true
and `now - g_climbLastAnim` is huge, giving gain 1.0 instantly. The MotionBlendMs
ramp added last round can never engage on the frame that matters. Fix: compute
`inputMotion` + `inputMotionAt` BEFORE the gain, require
`motionMatchesInput` (`g_climbMotion == inputMotion`), and ramp from
`max(g_climbLastAnim, inputMotionAt)`. The bottom block now reuses `inputMotion` as
`requested` so the two can never diverge.

(c) BODY CLIPPING IS THE STANDOFF NUMBER. `SurfaceOffsetMeters=0.16` positions the
ped ROOT off the fitted plane; torso/shoulders extend ~0.25 m ahead of the root, so
he intersected before any animation played. No amount of contact-fit work (centroid
-> most-protruding-point, hand-clearance correction) could fix a root placed inside
the surface. INI 0.30, `readF` default aligned 0.16 -> 0.30 (the declaration
initialiser was already 0.36 — they had drifted three ways).

Incidental: grip-hand alternation counted as a clip change and reset
`g_climbLastAnim`, dragging gain to 0 every 0.45 m of traverse (`gripSwapOnly` now
suppresses the reset); `_SET_ENTITY_ANIM_SPEED(-1.0)` was being applied to STATIC
grip poses (now only to genuinely directional traverse clips); and the trace's
`animPlaying`/`animPhase` hardcoded `kClimbAnimDict`, so it printed 0/0 for every
lateral and narrow-ledge frame — the diagnostic was lying to us about exactly the
subsystem that was broken. Now logs `animDict`, plus `motion` and `gain`.

INSTALLER BROKEN, UNRELATED: `Install-When-RDR2-Closes.ps1` line 9 copies
`CoreVignetteRamp\CoreVignetteRamp.ini`, which does not exist in the repo. With
`$ErrorActionPreference='Stop'` it aborts BEFORE line 10, so GameplayTweaks.asi is
never installed by that script. Copied the GameplayTweaks payload manually
(.asi unconditionally, .ini by the same hash rule, collectibles.csv). Anyone
relying on that script has been shipping stale ASIs.

NOT VERIFIED IN-GAME. Built Aug 5 07:27, installed, never run by me.


## #169 — four of five remaining defects, 2026-08-04

Build `D72A47C2CFF663A2659D7A43577B32CA494265AA278BDEB63178D81091E06258`.
Full restart required.

(a) Slide before the animation. The gate was `IS_ENTITY_PLAYING_ANIM(...)`, which
returns TRUE the moment `TASK_PLAY_ANIM` is issued — while the clip is still
blending in from the previous pose. So `motionAnimPlaying` was satisfied for the
entire blend and speed was already at full. Replaced the boolean gate with a
smoothstepped ramp over `[Climbing] MotionBlendMs` (220) measured from
`g_climbLastAnim`. Also fixes the abrupt start, since he accelerates in.

(b) Jutting rock vibration. The flank-probe block adopted `lead.normal` on any
frame where `turnDot` fell in (0.15, 0.96). On a convex edge the probe alternates
between the two faces, so the fit flip-flopped every frame — vibration, then
penetration, then a `lost_surface` release. Added a pending-normal latch: a
candidate must be reported with `dot > 0.97` against the previous candidate for
`[Climbing] SurfaceHoldMs` (180) before it is adopted. Any inconsistent frame
resets the latch.

(c) Mantle clip-through. `ToppingOut` lerped linearly from `g_climbTopOutFrom`
(on the wall face) to `g_climbTopOutTarget` (~0.80 m back from the lip, ground
+0.05). A straight line between those two points passes THROUGH the lip corner.
Replaced with a quadratic Bezier whose control point is directly above the wall
position at `max(from.z, target.z) + 0.35`, so he rises clear of the lip before
translating back onto the ledge.

(c2) Lateral animation. `kClimbSideClip` is
`script_story@fus1@ig@ig_1_cliffsidetraverse / cliff_p1_walk_loop_player` — a
story scene of a man walking sideways along a ledge with one arm extended. On a
climbing rig it reads as dancing / leading a horse, as reported. RDR2 authors NO
lateral wall-traverse clip anywhere (`mech_ladders` has none either), so there is
nothing correct to swap to. Sideways movement now alternates `base_left_hand_up`
/ `base_right_hand_up` every 0.45 m of travel, which reads as hand-over-hand.
`[Climbing] UseStoryLateralClip=1` restores the old clip.

STILL OPEN: (e) walking/sneaking off a climbable ledge should enter a downward
climb instead of stepping off. Not attempted in this build.

