# GitHub #144 - Movement Rework (Human)

## Requested player-visible contract

- On-foot movement has only walk and sprint: hold Shift to sprint; release it
  and Arthur immediately returns to walking.
- A base movement-rate setting scales the player before the separate sneak and
  sprint multipliers.
- Sneaking remains crouch-walk even while Shift is held; sneak-running is gone.
- Camps, interiors, towns, missions, aiming, wanted state and Stamina do not
  impose extra module-owned sprint restrictions.
- Existing #6 directional-dodge and #9 prone tasks must retain ownership while
  active.

## First installed runtime failure and exact cause

Lexer's first installed test held Shift and then released it while continuing
to move. Arthur returned to Rockstar's intermediate run/jog state and Stamina
continued to drain at the slower jogging rate.

The installed `GameplayTweaks.log` proves the gait implementation never ran in
that session. Every `[human-movement]` heartbeat from game ticks 266061421
through 266539984 reported `idle enabled=1 unavailable=1 frames=0`; there was
no gait transition, applied heartbeat, or release event in more than eight
minutes. Other systems simultaneously reported a live ped and control, so this
was not a loading/death session.

The exact source defect was treating `Player` as an entity handle:
`nonLocomotion` included `!player`. `PLAYER_ID()` is the valid local player
index **0** in Story Mode, so `!player` was true on every frame. The same handle
mistake also skipped the `PLAYER_CONTROL_ON(0)` readback. Consequently none of
the movement-rate, blend, motion-state, or release logic executed; vanilla
movement remained fully in control and produced the observed jog plus its
Stamina classification.

## Reference and primary evidence

The issue linked Nexus 8957, Walk Run Sprint Speed Control. Its public page
describes configurable walk speeds and hold-Shift locomotion; its public posts
also identify Rockstar's movement-blend bands (walk below the run band and a
sprint ceiling at 3.0). The page forbids adapting its files, so no code or asset
was downloaded or copied.

The issue also linked Nexus 1173, Fast Walking Outside Camp. Its public page
documents that the shipped brisk-walk gait works beyond camp and says source is
available under permissive terms, but no source archive was required. Its own
changelog warns that overriding scripted speeds affects mission pacing and that
older versions avoided aiming/shallow-water states. Lexer explicitly requested
removing ordinary when/where sprint restrictions, so the implementation accepts
mission-pacing changes while still yielding non-locomotion states such as water,
climbing, ragdoll and custom movement tasks.

The implementation is grounded in local primary files instead:

- `_downloads/RDR2_SDK/SDK/inc/natives.h` resolves
  `SET_PED_MOVE_RATE_OVERRIDE` (`0x085BF80FA50A39D1`), min/max movement blend,
  desired blend, and `FORCE_PED_MOTION_STATE`.
- `abigail2_1.c` forces the player/mission actors into `MOTIONSTATE_WALK` and
  the player into `MOTIONSTATE_CROUCH_WALK`; it also uses min/max and desired
  blend ratios.
- `mob1.c` forces `Global_35` into `MOTIONSTATE_SPRINT`.

## Issue-local implementation

`GameplayTweaks/modules/human_movement.cpp` separates gait from rate:

- no Shift: fixed `MOTIONSTATE_WALK`, blend 1.0;
- crouched/stealth, regardless of Shift: fixed `MOTIONSTATE_CROUCH_WALK`, blend
  1.0;
- Shift held while moving: fixed `MOTIONSTATE_SPRINT`, blend 3.0;
- rate override: `BaseMoveRate`, multiplied by `SneakMultiplier` or
  `SprintMultiplier` for those modes and bounded to 0.10..3.00.

The repaired module reads enabled and disabled `INPUT_SPRINT` in control groups
0 and 2 plus physical Shift, then disables that Rockstar action while it owns
ordinary on-foot movement. The module therefore owns hold/release semantics
instead of allowing Rockstar's run-toggle/cycle latch to survive release. It
deliberately has no camp, interior, mission, aiming, wanted or Stamina gate.

`Player` is no longer null-tested because zero is a valid player index; only the
ped entity is handle-validated. The integration `callerUnavailable` hint is no
longer itself a gate. The module derives ownership from live fade/control/menu
state and direct #6 dodge, #9 prone, and #97 climbing state. The module also
retains the physical mount, swim,
native climb/ladder, fall, ragdoll/get-up, and native-prone gates. This preserves
those other body owners without allowing an opaque, uncorroborated caller flag
to silently suppress the entire feature. The idle heartbeat now prints every
individual gate term.

The rate/blend/motion calls are per-frame because they compete with Rockstar's
per-frame player controller. On the sprint-to-walk edge the module applies walk
in that same update and retains a release latch until three consecutive moving
frames read back `IS_PED_RUNNING=0`, `IS_PED_SPRINTING=0`, and desired blend no
higher than Rockstar's 1.5 walk ceiling. A rejected readback is rate-limited and
records the actual states plus whether `FORCE_PED_MOTION_STATE` accepted the
request. The five-second heartbeat records the same live postconditions.

## Integration and Stamina reconciliation

The integration owner must include this module after `movement.cpp` and call
`updateHumanMovementRework(player, ped, now, unavailable)` every frame.
`unavailable` must include #6 dodge, #9 prone, custom climbing and normal
non-locomotion/loading ownership, but must not include the broad `mission` gate
or ordinary camp/interior/aim/wanted/Stamina restrictions.

The existing Stamina controller already classifies actual sprint before run and
walk. Because this module produces no run gait, `JoggingRate` becomes unreachable
and must be removed from the integration-owned `[HumanStamina]` presentation;
walking/sneaking use `WalkingSneakingRate` and sprint uses `SprintingRate`.
No Stamina implementation was duplicated in this issue-local module.

## Static result and runtime boundary

`python tools/reverse-engineering/verify_human_movement_issue_144.py` verifies
the five native hashes, five direct Story-script mechanisms, three exact gait
branches, the valid player-index-zero rule, direct #6/#9/#97 ownership, sprint
control consumption, release ordering and the three-frame live readback latch,
sneak precedence, restoration, exclusions, and the absence of
run/task/velocity/teleport mechanisms.

Runtime acceptance remains required:

1. WASD without Shift walks; pressing and holding Shift goes directly to sprint;
   releasing Shift returns to walk without a jog/toggle latch.
2. The same transition works in camp, town, interiors, during allowed mission
   locomotion and while aiming, subject only to animation feasibility.
3. Crouched/stealth movement never runs or sprints when Shift is held.
4. Each of the three rate settings visibly changes only its intended speed, and
   the log's selected rate matches the configured product.
5. #6 directional dodge, #9 prone, climbing, swimming, falls/ragdoll, mounts,
   interactions and cutscenes retain control and restore the movement override
   cleanly afterward.
6. Stamina uses only standing/walking-sneaking/sprinting modes; sprint drains at
   `SprintingRate` and release returns to the configured walking recovery/rate.
## 2026-08-10 combined release

- Release ASI built successfully: `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`.
- RDR2 was running, so one hidden payload-only installer was queued. The issue remained actionable pending game-root hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.

## 2026-08-10 immediate movement failure and FWOC isolation

- The first live test of the combined build produced severe animation
  stuttering/acceleration as soon as the player attempted to move.
- The installed log showed this module repeatedly owning the locomotion state;
  the `[HumanMovement]` section was hot-disabled and the same live log then
  confirmed `enabled=0`.
- A second locomotion ASI was still installed: FWOC - Fast Walking Outside
  Camp, deployed as `FastWalk.asi` in the game root. That exact file was moved
  to `mod storage\disabled\FWOC\FastWalk.asi`; its SHA-256 before and after the
  move matched. Because the current RDR2 process had already loaded the ASI,
  isolation does not take effect until the next game restart.
- The issue returned to `actionable`. A restarted session with FWOC absent and
  Human Movement disabled is the clean baseline; the custom movement feature
  must not be re-enabled or returned to `test me` until its ownership conflict
  is repaired and a new combined build is installed.

## Recurrence audit before the post-failure repair

### Primary evidence / reference

- Live issue comment `#issuecomment-5239884895` records the catastrophic
  immediate animation failure, the hot-disable, and the fact that the already
  running process still contained FWOC even after `FastWalk.asi` was removed.
- The installed unified log is the execution record: 2,867 owned frames were
  applied before `[HumanMovement] Enabled=0` was read back and subsequent
  heartbeats remained idle. The failure happened while the module was actively
  writing locomotion state; it was not an unexecuted-path result.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/` is the authority for any
  engine-sanctioned movement-controller path. A Story script using a motion
  native in a bounded scene is not evidence that repeatedly forcing it from an
  always-on player controller is safe.

### Sanctioned path and failed engine fight

The failed build selected a motion state every frame and simultaneously pinned
minimum blend, maximum blend, and desired blend to the same value. That is now
a documented failed engine fight. Reissuing `FORCE_PED_MOTION_STATE` and
collapsing the blend range every update can continuously restart/reselect the
locomotion graph and leaves no interpolation range for the graph to solve. It
must not be cosmetically rate-limited or rearranged. The replacement must let
Rockstar own animation/state transitions and use only a supported input gate
and a non-collapsed blend ceiling/rate scalar where evidence permits.

### Actual execution / postcondition

An implementation attempt is not accepted from setter calls. Its diagnostic
must distinguish disabled, no movement input, walk clamp active, sprint input
passed through, and sneak sprint blocked. Readbacks must record
`IS_PED_RUNNING`, `IS_PED_SPRINTING`, desired movement blend, and entity speed.
On Shift release, three consecutive moving-frame readbacks must show neither
run nor sprint and a walk-band desired blend. If those postconditions do not
appear, the mechanism executed but did not satisfy the issue.

### Player-visible acceptance

Acceptance requires a clean RDR2 restart with `FastWalk.asi` absent. With Human
Movement enabled only in a subsequently integrated test build: ordinary WASD
must animate smoothly at walk, held Shift must use Rockstar's natural sprint,
release must return directly to a smooth walk without jog/run retention, and
crouch/stealth plus Shift must remain a smooth crouch-walk. No stutter,
accelerated animation cycling, skating, or graph resets are acceptable. Until
that clean-restart test exists, `[HumanMovement] Enabled=0` remains the safe
installed state and the issue remains actionable.

### Per-frame native inventory

The failed controller wrote these natives every owned frame:
`SET_PED_MOVE_RATE_OVERRIDE`, `SET_PED_MIN_MOVE_BLEND_RATIO`,
`SET_PED_MAX_MOVE_BLEND_RATIO`, `SET_PED_DESIRED_MOVE_BLEND_RATIO`, and
`FORCE_PED_MOTION_STATE`. It also read `IS_PED_RUNNING`, `IS_PED_SPRINTING`,
and the desired move blend every frame. The four blend/motion-state writes are
not permitted in the replacement as a collapsed per-frame graph override.
`SET_PED_MOVE_RATE_OVERRIDE` may remain only because Rockstar defines it as a
frame-scoped scalar; its cadence and readback must remain explicit. Any
per-frame maximum-blend ceiling must remain a ceiling (minimum stays zero), be
documented as a clamp rather than a graph-state request, and never be combined
with desired-blend or forced-motion writes.

## Post-failure source repair (not enabled or installed)

The direct runtime cause is no longer attributed only to FWOC contention. The
installed log proves the GameplayTweaks controller itself ran 2,867 owned frames
before hot-disable. On every one of those frames it called
`FORCE_PED_MOTION_STATE` and wrote the same value to minimum blend, maximum
blend, and desired blend. Even without FWOC in a new process, that combination
reselects the motion state and leaves the graph no interpolation range. It is a
self-contained stutter/acceleration mechanism.

`GameplayTweaks/modules/human_movement.cpp` now removes the engine fight rather
than rearranging it:

- no call to `FORCE_PED_MOTION_STATE`;
- no desired-blend write;
- no per-frame minimum-blend write or min=max pin;
- ordinary and crouched frames block Rockstar's Sprint control and set only a
  maximum blend ceiling of 1.0;
- standing held-Shift frames leave Rockstar's Sprint control enabled and use a
  maximum ceiling of 3.0, so Rockstar owns the natural sprint transition;
- `SET_PED_MOVE_RATE_OVERRIDE` remains the configured frame-scoped rate scalar;
- release still requires three consecutive moving-frame postconditions with no
  actual run/sprint and desired blend in the walk band.

`restoreHumanMovementDefaults` may write minimum 0, maximum 3, and rate 1 only
on an ownership/yield edge. It is not an active-frame gait pin.

Scoped verifier result:

`PASS: #144 uses only a frame-scoped rate scalar and non-collapsed maximum-blend ceiling; Rockstar owns walk/sprint animation transitions`

The shared `[HumanMovement] Enabled=0` setting was deliberately not changed.
No compile, build, install, or label change was performed. Runtime acceptance
starts only after a clean restart proves `FastWalk.asi` is absent from the new
process and Human Movement is still disabled. The integration owner may then
build this source, but must keep the feature disabled until a deliberately
enabled clean-session test can check smooth walk, natural held-Shift sprint,
immediate smooth walk on release, and no crouch sprint. Static checks do not
prove those animation postconditions.

## 2026-08-10 #156/#157 ownership reconciliation

The two returned gait issues were repaired in this same module instead of
adding writers to `movement.cpp`. The #6 reference sequence remains owned by
`g_dodgeRollStage`; custom prone and climbing retain their existing direct
gates. The ordinary gait path now has one explicit `sprintAllowed` decision:
standing held Shift outside a release-confirmation window passes Rockstar's
Sprint input; crouch/stealth, released Shift and a pending release all block it.

The release window retains the 1.0 ceiling until three consecutive live
no-run/no-sprint/walk-blend readbacks, and logs the first owned frame separately.
Crouch movement records its own consecutive no-run readback and bounded failure
line. These are postcondition/ownership corrections; the catastrophic forced
motion state, desired blend and min=max pin remain absent.

The shared feature remains disabled in the INI and this issue-local pass did not
change that integration-owned state. A clean restarted runtime with the module
deliberately enabled remains required for #144, #156 and #157 together.

## 2026-08-10 recurrence audit for #71 speed reconciliation

### Primary evidence and single-owner rule

The live #71 comment asks for independent on-road foot and horse speed
multipliers. It does not authorize a second human locomotion writer. The
post-failure #144 evidence still controls: 2,867 frames of forced state plus
collapsed blend pinning produced catastrophic stutter, so road speed must be a
plain factor in this module's existing frame-scoped rate scalar.

### Sanctioned path and postcondition

For an owned ordinary human frame, compute `BaseMoveRate * gait multiplier *
stable road multiplier`, then make the same one
`SET_PED_MOVE_RATE_OVERRIDE` call and the same non-collapsed maximum-blend
ceiling call. The road state must not change sprint gating, release ownership,
crouch ownership, #6 dodge, #9 prone, or climbing. Heartbeats must expose road
state, the road factor, composed rate, actual run/sprint, desired blend and
entity speed so "setter executed" cannot be reported as visible success.

### Player-visible acceptance and enable boundary

Human Movement remains unsafe to enable by default until one clean restarted
session, with FWOC absent, proves smooth walk/sprint/release/crouch behavior.
That same session must compare a fixed foot gait on-road and immediately
off-road, with `RoadSpeedMultiplier=1.0` restoring the baseline. No road factor
may introduce stutter, animation acceleration, skating, an intermediate run on
release, or crouch sprint.

### Per-frame native inventory

This reconciliation adds no per-frame native. `IS_POINT_ON_ROAD` is supplied
by #71's bounded cache (100 ms samples, two changed samples to transition).
The existing human `SET_PED_MOVE_RATE_OVERRIDE` remains the only rate writer;
the existing `SET_PED_MAX_MOVE_BLEND_RATIO` remains a ceiling. Desired-blend,
minimum-blend and forced-motion writes remain forbidden in active frames.

## #71 composition result

`human_movement.cpp` now hot-reads
`[HumanMovement] RoadSpeedMultiplier=1.0` and composes the stable #71 road
factor into the existing gait rate before its one active-frame move-rate call.
The transition and heartbeat diagnostics expose `onRoad`, `roadFactor`, the
final composed `rate`, live run/sprint state, desired blend and entity speed.
No control, blend, motion-state, task or additional locomotion write was added.

The #144, #156, #157, #6 and 34-invariant #9 parity static checks all still
pass after composition. This establishes single-writer/source compatibility,
not player-visible animation safety. Human Movement cannot yet be safely
enabled in the ordinary shared INI: it must remain disabled until a clean RDR2
restart with FWOC absent proves smooth walk, natural sprint, direct release to
walk, no crouch sprint, and the on-road/off-road rate difference without
stutter, skating or accelerated animation cycling.
# 2026-08-10 integration test enablement

After the graph-pinning implementation was removed, the combined static suite
passed #6, #9/#97 parity, #71, #144, #156, and #157 together, and the separate
FWOC/FastWalk ASI was confirmed absent from the game root. Integration then
changed `[HumanMovement] Enabled` from 0 to 1 specifically so the corrected
candidate can receive the required clean-start runtime test. This is not
behavior acceptance: the setting hot-reloads, so any recurrence can be disabled
without another restart, and the four coupled issues remain unaccepted until
Lexer observes smooth walk/sprint/release/crouch behavior and road composition.

## 2026-08-10 recurrence audit for the returned speed-setting failure

### Executed path and failed postcondition

The installed unified log proves that the controller executed. With
`BaseMoveRate=2` and `SprintMultiplier=1`, both the walk and sprint branches
reported `rate=2`. Stable walk readbacks were about 1.2-1.4 m/s, while stable
sprint readbacks were about 5.6-6.8 m/s. Therefore the same value passed to
`SET_PED_MOVE_RATE_OVERRIDE` did not produce the same world speed. The former
diagnostic proved only the setter argument. It did not prove the requested
speed.

### Primary evidence and supported boundary

`_downloads/RDR2_SDK/SDK/inc/natives.h:5306-5308` and the matching
`_downloads/natives.json` entry for hash `0x085BF80FA50A39D1` define
`SET_PED_MOVE_RATE_OVERRIDE` with a minimum of 0.0 and a maximum of 1.15. The
module's 2.0 base limit, 3.0 multiplier limits and 3.0 final limit were invented
outside that contract. One Story NPC call passes 1.75, but an out-of-contract
mission call is not evidence that a permanent player controller supports that
range.

The two issue-linked prior-art pages do not supply the missing absolute-speed
mechanism. Nexus 8957 says that its locomotion speeds are configurable, but its
public page does not expose the implementation or show that one value produces
one world speed across different gait bands. Nexus 1173 says that it exposes
Rockstar's existing brisk-walk animation outside camp. It does not claim to
scale a sprint animation to an exact walking speed.

### Sanctioned path and excluded recurrence classes

The only evidence-backed issue-local write remains the native rate scalar,
bounded to its documented 0.10-1.15 user range, plus the existing non-collapsed
maximum-blend ceiling. The scalar is relative to the locomotion graph's selected
gait. It is not metres per second. Equal scalar values cannot be described as
equal gait speeds.

This repair must not add forced motion states, desired-blend writes,
active-frame minimum-blend writes, coordinate changes, entity velocity writes,
or a feedback controller that fights the animation graph. It must preserve
#71's single road-factor composition, #156's sprint-release ownership, and
#157's crouch/sprint ownership.

### Player-visible acceptance boundary

Static evidence can prove the supported scalar range and prevent false labels,
units, and logs. It cannot prove an exact equal-speed sprint animation because
the sanctioned native does not offer an absolute speed target. Runtime can only
confirm that each in-range scalar changes the selected gait smoothly and that
the log reports both the requested scalar product and the bounded value actually
sent to the native. Issue #144 remains unaccepted while its requested true-speed
semantics exceed that engine path.

## Supported-range correction

`human_movement.cpp` now uses 0.10-1.15 for the base, sneak, sprint, and final
native scalar ranges. It retains the raw base/sneak/sprint values only for
diagnostics. Each gait transition and heartbeat now reports `requestedRate`,
the bounded `rate` sent to the native, and `nativeRangeClamped`. Thus the current
`BaseMoveRate=2` test value will be reported as requested 2 and applied 1.15,
not as a successful rate-2 write.

The settings schema now calls these values gait-rate scalars, shows `x` instead
of `points/s`, limits each control to 1.15, and explicitly says that equal walk
and sprint values do not produce equal world speeds. The user's current INI
test value was not overwritten.

The scoped checks passed:

- `verify_human_movement_issue_144.py`
- `verify_roads_issue_71.py`
- `verify_human_movement_issue_156.py`
- `verify_human_movement_issue_157.py`
- `verify_settings_menu_issue_18.py`

These results prove source ownership, the native range, truthful presentation,
and the absence of the known graph-fight mechanisms. They do not prove a new
absolute-speed feature. No build, install, GitHub comment, label, or state
change was performed.

## 2026-08-11 supported-subset repair

### Recurrence checks

This pass re-read `fuckups.txt`, the complete live issue and comments, this
worklog, the module, the SDK native declaration, and the installed unified log.
The relevant recurrence risks were invented ranges, a setter-call log treated
as a postcondition, forced animation-graph ownership, and settings whose names
claimed semantics that the native does not have.

The current installed log reports `enabled=0` and `frames=0`, so it proves only
that Human Movement is disabled in the running build. The prior enabled trace
remains the execution evidence: the controller applied frames, but Rockstar's
sprint readback remained active for as much as 343 ms after Shift release.
That measured blend time disproves the former claim of an immediate transition.

### Source and settings correction

The module now reads three independent hot-reloaded settings:

- `WalkRateScalar`;
- `SneakRateScalar`;
- `SprintRateScalar`.

Each value is clamped to the SDK's documented 0.10-1.15 native range. The old
`BaseMoveRate`, `SneakMultiplier`, and `SprintMultiplier` model was removed from
the issue-owned source and settings fragment because base-times-multiplier
wording implied a cross-gait speed relationship that does not exist.

The controller still applies only a relative gait scalar and a non-collapsed
maximum-blend ceiling. It does not force a motion state, write desired blend,
write active-frame minimum blend, set velocity, move coordinates, or play a
replacement locomotion animation. Walk frames block Sprint and use the walk
ceiling. Held-Shift standing frames pass Sprint to Rockstar and use the sprint
ceiling. Sneak frames take precedence, block Sprint, and use the walk ceiling.
The road factor from #71 composes after the selected gait scalar and remains a
separate relative factor.

Release diagnostics now describe the first owned frame and the continuing
engine transition without claiming success. A confirmed line is emitted only
after three consecutive readbacks show no run, no sprint, and desired blend in
the walk band. The measured transition is not an extra stable run mode, but it
is not instantaneous.

### Exact supported behavior and remaining boundary

The supported candidate can provide walk as the ordinary standing state,
Rockstar's sprint while Shift is held, no crouched sneak-run, and no added
camp/interior/mission/aim/wanted restriction when Rockstar has not assigned a
different movement task. It can provide independent relative rate scalars for
walk, sneak, and sprint. It cannot provide an absolute metres-per-second target,
make equal scalar values produce equal gait speeds, or remove Rockstar's short
sprint-to-walk animation blend without returning to the graph-fight mechanisms
that already caused catastrophic movement.

Static checks passed for #144, #156, #157, #71, the prone/climb parity set, #6,
and #9. These checks prove source ownership, documented ranges, absence of the
known unsafe mechanisms, and diagnostic structure. They do not prove smooth
in-game animation or player-visible gait behavior. No compile, install,
manifest, shared INI/schema, GitHub label, comment, or state change was made.
