# GitHub #9 - Prone backwards launch

## Diagnosis

The live issue reported that briefly pressing W while prone launched Arthur
backwards at extreme speed. The installed runtime trace proved this was not an
input-scale problem: commanded crawl drive was about `0.83`, yet the entity
moved `0.68 m` in one 250 ms trace interval and then continued moving
`0.66-0.79 m` per interval after input returned to zero and the code wrote zero
horizontal velocity. An earlier sample continued at roughly `0.8-1.4 m` per
interval after the switch to idle.

The decompiled Crawl N' Gun reference uses task mask `0x30001C01` for moving
crawl clips and `0x30000401` for idle (`_analysis/reference-decompilation/
Dive-Crawl-N-Gun.c`, around lines 12307-12318 and 12363-12370). The extra mover
bits are valid when the clip owns displacement. This implementation also drove
camera-relative translation with `SET_ENTITY_VELOCITY`, so it had two movement
owners. The animation mover could update the transform independently of the
velocity cap and survive the blend back to idle. The large authored lateral
movers in `walk_turn_l4/r4` made that conflict worse.

## Implementation

- Moving crawl now uses the idle/no-mover loop mask `0x30000401`; `walk` is a
  cosmetic loop while the existing camera-relative controller solely owns
  horizontal displacement.
- Removed the lateral turn-cycle selection. Heading still interpolates at the
  configured turn rate, but no large authored turn mover can be layered over it.
- Reset the displacement baseline when the authored entry finishes, so the
  entry clip is never mistaken for bad crawl movement.
- Added a frame-local containment envelope. If a stale blended mover produces
  impossible horizontal displacement or moves opposite the requested
  direction, the frame is restored to the last valid X/Y, horizontal velocity
  is cleared, Z is preserved, and the event is written to the prone trace. This
  is a backstop for engine blending, not the ordinary movement path.

## Static evidence

- The moving task has exactly one `kProneCosmeticLocoFlags` use and no turn-clip
  symbols remain.
- The stale-mover containment and entry-baseline reset are both present.
- `git diff --check -- GameplayTweaks/modules/movement.cpp` passed (the normal
  checkout line-ending warning remained).

`tools/reverse-engineering/verify_prone_climb_parity.py` is integration-owned
and still encodes the obsolete root-motion-only design: it requires
`0x30001C01` and rejects the explicit velocity controller that was already in
the source before this fix. Integration must replace that required token with
`kProneCosmeticLocoFlags = 0x30000401`, remove the obsolete derived-velocity
rejection, and add an invariant for `contained stale crawl mover` before using
the verifier as a gate.

## Integration and acceptance

No dispatcher or INI change is needed. Rebuild the generated knowledge indexes,
update the integration-owned verifier as described above, build/install the
single ASI, and hash-verify it. In game, enter prone on flat ground, tap W once,
release it, then repeat while changing camera heading and with diagonal input.
Arthur must move only at configured crawl speed, stop immediately on release,
never continue backwards, and turn gradually without a lateral launch. Check
`GameplayTweaks.prone.log` for `contained stale crawl mover`; seeing it means
the safety net prevented an engine-blend displacement and should include the
measured distance.

## Follow-up after the failed installed test

The installed build still slid rapidly whenever W was pressed and its entry
visibly turned Arthur 90 degrees left. That disproved the earlier claim that a
no-mover task flag plus a velocity cap was sufficient.

The corrected controller does not advance from `ENTITY_COORDS`, because those
coordinates already include any transform applied by the animation task since
the preceding script frame. It now advances from `g_proneLastPosition`, the
last coordinate committed by this controller, by at most one configured crawl
step. With no input it explicitly restores the same committed X/Y. Horizontal
velocity is zeroed in both paths. Animation and physics movement arriving
between frames is recorded for diagnosis but never becomes the next frame's
movement base. Teleports larger than 15 metres still exit prone before the
anchor can restore the old position.

The quarter-turn was authored by `mech_crawl@base/idle2stealth`; preserving
entity heading could not remove a turn inside the animation itself. Entry now
uses the shipped neutral `mech_crawl@base/idle_intro` clip, still after forced
crouch, and retains the heading hold as a second guard.

`python tools/reverse-engineering/verify_prone_issue_9.py` passed 10 issue-local
transform-ownership invariants. The combined reference verifier also passed 33
invariants, and `git diff --check` passed apart from the checkout's normal LF to
CRLF warning. This source has not been built, installed, or tested in game; #9
therefore remains actionable for integration.

## Current actionable pass

`mech_crawl@base/idle_intro` was removed after the shipped animation evidence
failed to validate it. Entry now goes through crouch and the known directional
get-up/prone asset; exit is an authored prone-to-knees-to-crouch-to-stand path,
with immediate cancellation reserved for hard interruptions. The issue verifier
and the 33-invariant movement parity suite pass. This attempt is not installed.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-10 actionable correction: port the working reference entry

The installed test rejected the cop injury/get-up `front_to_prone` clip: Arthur
crumpled sideways, spun, and exposed an A-pose. The supplied Crawl N' Gun binary
does not use that clip. Its decompilation selects the weapon-aware
`mech_weapons_core@base@dive@{unarmed,pistol,rifle}@launch` dictionary,
`dive_launch_fwd`, and task flags `0x30014C12` before entering the crawl loop.

The prone state machine now retains the visible crouch stage Lexer requested,
then plays that exact reference transition using the held-weapon class. All
three dictionaries are streamed through the existing bounded loader. The
rejected `front_to_prone`, `idle_intro`, and `idle2stealth` entry paths are
absent from `beginProne`. `verify_prone_issue_9.py` passes 18 invariants and the
release build compiles. This still requires in-game confirmation after the
combined hash-verified install, so #9 remains `actionable` until then.

## 2026-08-10 correction: persistent prone is not the combat-dive handler

The preceding pass conflated two separate functions in the supplied working
Crawl N' Gun decompilation. `FUN_180015400` is its combat-dive handler; that is
where `dive_launch_fwd` and flags `0x30014C12` occur. Porting that clip into the
stationary crouch-to-prone state transition caused the installed result Lexer
reported: Arthur dove into the ground and ragdolled.

The persistent-prone input handler is `FUN_180014d60`. Its exact entry is:

- enable crouch with `_SET_PED_CROUCH_MOVEMENT`;
- play `mech_crawl@base/idle2stealth` with positive `1.0/1.0` blends,
  indefinite duration and task tail `0x02000000`;
- use flags `0x00010C00` for keyboard or `0x20010C00` for controller, selected
  by `_IS_USING_KEYBOARD` (`0xA571D46727E2B718`);
- wait 900 ms before handing off to the crawl loop.

The active state machine now retains its visible bounded crouch stage and
heading guard, but issues that exact persistent-prone task contract instead of
any dive asset. The three unnecessary weapon-specific dive dictionaries were
removed from the entry loader. The stage now calls only
`_SET_PED_CROUCH_MOVEMENT`, as the reference does; it no longer also enables
native stealth movement while `idle2stealth` is trying to own that transition.
The rejected injury transition and unverified `idle_intro` remain absent.

`python tools/reverse-engineering/verify_prone_issue_9.py` passes 20
reference-entry and transform-ownership invariants. It verifies the persistent
entry tokens against `FUN_180014d60` and independently verifies that
`dive_launch_fwd` belongs to `FUN_180015400`. The integration-owned combined
`verify_prone_climb_parity.py` still requires the now-rejected
`0x30014C12` dive entry and therefore reports
`missing invariants: reference dive entry flags`; integration must update that
stale invariant before using the combined suite as a gate.

No build, install, dispatcher/INI/shared-file edit, GitHub label change, commit
or push was performed. Runtime acceptance remains required: standing and
crouched holds must visibly pass through crouch into face-down prone without a
dive, ragdoll, spin or A-pose; heading must stay stable; idle/crawl/stop and
both exits must retain their prior acceptance checks.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
## fuckups.txt recurrence audit

- The earlier pass confused the reference mod's combat-dive function with its persistent-prone entry. That was a guessed call-site substitution, not reference parity.
- The replacement uses only the indexed `mech_crawl@base/idle2stealth` contract with the reference flags and a survival readback. Static parity is not visual acceptance; prone entry, idle, movement, weapons, and exit remain runtime checks.

## 2026-08-10 returned-test audit: the reference stopped at entry

The latest installed result was still wholly rejected. The source called its
entry "reference" while replacing the reference mod's entire post-entry crawl
loop with a project-invented controller. Each prone frame could write X/Y
coordinates, horizontal velocity, entity heading, pitch/roll and floor height,
then run `mech_crawl@base/walk` with a non-reference no-mover flag. The working
reference does none of those transform writes: after the 900 ms entry it uses
the crawl clips themselves as the sole locomotion owner with `0x30001C01`, and
uses `0x30000401` only for idle. The claimed parity therefore ended exactly
where the player-visible failure began.

The active trace was also unavailable in the release session because
`proneLog()` discarded every line unless runtime development mode was enabled.
That guaranteed another blind returned test despite `DevelopmentTrace=1` in the
installed INI.

This correction removes the custom coordinate/velocity/rotation/floor writer
from ordinary prone locomotion, issues the reference crouch +
`idle2stealth` task without the invented 180-700 ms pre-task staging delay,
uses the reference positive blends and mover/idle flags, and emits bounded
always-on transition/postcondition records. This is still not in-game
acceptance; it must not be described as fixed until Arthur visibly enters,
crawls, stops and exits without an A-pose, spin or launch.

## 2026-08-10 recurrence audit before the camera-relative and exit repair

- The latest accepted behavior was explicit: a normal prone-to-standing exit
  had to visibly pass through crouch, and held forward crawl had to continue
  following the camera as the camera turned.
- Primary evidence was the supplied binary
  `_downloads/crawl-n-gun-reference/extracted/Dive - Crawl N' Gun.asi`
  (SHA-256
  `489FC00A5FB994208C0178595E141CB1D4F5A3CC17B9316E414B0E57B36BBBAF`)
  and its decompilation. `FUN_18000f280` read the four movement controls but
  disabled only `INPUT_JUMP` (`0xD9D0E1C0`) and
  `INPUT_DYNAMIC_SCENARIO` (`0x2EAB0795`). It never disabled the LR or UD
  movement axes. The active port disabled both axes every prone frame, which
  removed Rockstar's native camera-relative steering while the authored crawl
  mover kept advancing along its original heading.
- The same reference loop exited through dictionary address `0x180044F48`
  (`ai_getup@directional_sweep@combat@cop@rifle@front`) and clip address
  `0x180044ED0` (`get_up_0`) with flags `0x20002C10`, waited exactly 600 ms,
  then called `_SET_PED_CROUCH_MOVEMENT(ped, true, 1, true)` before clearing
  secondary and primary tasks. The active port substituted
  `prone_to_knees@crawl/front` and waited for its full duration. That was not
  the supplied working exit contract.
- The recurring failure classes were an invented replacement for an available
  reference path, competing transform ownership, and call-site-only evidence.
  This pass could not add coordinate, velocity, heading, rotation, floor,
  dive, ragdoll, A-pose, or generic locomotion control. It also could not call
  a task issued "successful" without a state/readback boundary.
- The sanctioned repair was to keep the exact reference root-motion clips,
  leave LR/UD available to Rockstar as the reference did, use the exact
  reference standing exit, and confirm the intermediate native crouch state
  before requesting Rockstar's normal crouch-to-stand transition.
- Static proof had to hash-pin the supplied ASI, verify the decompiled input
  and exit contracts, reject every forbidden transform writer in ordinary
  prone locomotion, and preserve all adjacent climb/roll/human-movement
  verifiers. Player-visible acceptance remained a continuously camera-relative
  held-W crawl and a visible prone-to-crouch-to-standing exit.

## 2026-08-10 reference-grounded repair

Two independent source defects matched the returned result.

First, the port disabled `INPUT_MOVE_LR` and `INPUT_MOVE_UD` every prone frame.
The supplied reference does not. The authored crawl task therefore kept moving
on its initial root heading while Rockstar could no longer receive held W and
steer that root as the camera changed. Those two disables were removed. The
reference walk, turn and backward clips remain the only crawl mover; this pass
added no coordinate, velocity, heading, rotation, floor, dive, ragdoll or
generic locomotion controller.

Second, `finishProneExit` entered `SettlingStanding` and then immediately set
`g_pronePed` to zero. Because that state still counted as a custom prone
transition, the next update saw `ped != g_pronePed` and ran the hard-interrupt
exit. The intended 300 ms crouch seat could never execute. The normal standing
path also used the substituted `prone_to_knees@crawl/front` clip rather than
the supplied mod's exit.

The standing path now uses the binary's exact
`ai_getup@directional_sweep@combat@cop@rifle@front/get_up_0` task with flags
`0x20002C10` and its exact 600 ms boundary. It then calls the resolved
`_SET_PED_CROUCH_MOVEMENT(ped, true, 1, true)` before clearing secondary and
primary tasks, preserves ped/model ownership through `SettlingStanding`, and
arms the existing 300 ms seat only after crouch readback is true. It requests
Rockstar's non-immediate crouch-to-stand transition afterward and does not
release state ownership until crouch readback becomes false. Bounded failure
records distinguish a rejected crouch handoff or stand request from an
unexecuted path.

The release trace now records movement distance, camera yaw, ped heading and
the horizontal movement-to-camera dot product. This is read-only evidence: a
held-W camera turn should remain near `movementCameraDot=1` after steering
settles, while the visual transition remains Lexer's acceptance boundary.

`verify_prone_issue_9.py` now hash-pins the supplied ASI, resolves the two exit
strings directly from PE virtual addresses, verifies the decompiled disable
set and exact exit order, rejects LR/UD suppression, and checks both native
crouch readbacks. Its 31 guards passed. Prone/climb parity, #68, #6/#172/#173,
all #97/#113/#119/#159/#160/#161/#165/#166/#167/#169 climbing checks, and
#144/#156/#157 human-movement checks also passed. `git diff --check` passed
apart from the checkout's normal LF-to-CRLF warning.

No build, install, shared dispatcher/INI edit, GitHub change, commit or push was
performed. Runtime remains decisive: hold W, rotate the camera through a clear
angle, and confirm Arthur continuously follows it; then use the standing exit
and confirm the reference get-up visibly seats him in crouch before Rockstar's
crouch-to-stand transition completes.

## 2026-08-11 returned camera-relative test

The installed test disproved the previous camera-relative claim. The source
read the gameplay-camera yaw, calculated `proneTurnDelta`, and wrote that value
only to the trace. It never applied the configured `TurnDegreesPerSecond` to
Arthur. The authored `walk` root mover therefore kept the heading it had when
the task began, exactly as Lexer reported.

The repair keeps the reference crawl clips as the only translation owner. While
movement input is live, it turns only the ped's base yaw toward
`GET_GAMEPLAY_CAM_ROT(2).z`, bounded by `TurnDegreesPerSecond * dt`. It reads the
accepted heading back immediately and records requested yaw, remaining error,
and readback yaw. It adds no coordinate, velocity, pitch, roll, floor, or task
writer.

The current unified log does not contain the prone exit that Lexer described as
hitching. It contains only idle gate records from the later session, so it
cannot prove where that older visual discontinuity occurred. The source already
retains the live crawl task until the authored `get_up_0` exit is issued and
keeps the reference crouch-before-clear order; static code cannot establish
that the visible blend is smooth.

`verify_prone_issue_9.py` passed 34 entry, root-motion, bounded-yaw, and
readback checks. The integration-owned parity verifier still has the superseded
blanket ban on `SET_ENTITY_HEADING`; integration must narrow it to allow this
one bounded live-prone yaw owner while continuing to reject coordinate,
velocity, pitch/roll, floor, and freeze writers.

No build, install, shared-file edit, GitHub mutation, commit, or push was
performed. Runtime acceptance is held W following a rotating camera without a
slide or snap. The standing exit still requires visual confirmation because no
surviving trace captured the reported hitch.
