# GitHub #8 - In-game camera editor

## Recurrence audit — tilde developer-mode boundary

- **Primary evidence/reference:** the latest live owner comment says developer
  tools should not be compiled out merely because the ordinary release build is
  used: tilde toggles developer mode, and the tools are available only while
  that runtime mode is on. Current `script.cpp` is the counter-evidence: its
  runtime predicate includes `GameplayTweaksBuild::Development`, and its tilde,
  F2, and F3 authoring paths sit behind `#if GAMEPLAYTWEAKS_DEV_MODE`.
- **Sanctioned path:** one shared runtime developer-mode boolean, default off in
  every build, owns the tilde edge. Every authoring input must independently
  require `developmentModeActive()`. The camera module consumes that shared
  predicate only; it must not create a private release-only editor mode or
  toggle tilde a second time. Removing compile-time exclusion is distinct from
  making authoring inputs permanently active.
- **Execution proof:** the shared tilde handler must log the new runtime mode;
  the camera's bounded heartbeat must report that same mode and final editor
  state; Numpad 0 must log which editor received ownership. These records
  distinguish a missing dispatcher, an untoggled mode, and keypad contention.
- **Rendered/player-visible acceptance:** in a normal combined build, tilde-on
  must visibly show the camera calibration overlay and allow keypad adjustment;
  Numpad 0 must swap to/from the fortification editor. Tilde-off must remove both
  editor overlays and leave F2/F3 and all other authoring inputs inert. Static
  source checks alone do not satisfy this acceptance boundary.
- **Per-frame mutation:** the gameplay-camera parameter and LOW/NORMAL natives
  are intentionally frame-scoped camera controls and continue independently of
  whether the authoring overlay is open. Authoring input/persistence writes are
  transition-driven only and must never run while developer mode is off.

## Requested behavior

The live camera calibration overlay must cover standing, crouched, horseback,
vehicle and aim cameras, and must expose every real camera-position control the
engine supplies without presenting a slider that does nothing. Prone remains an
additional mod-owned stance profile.

## Native audit

The local RDR3 native database gives `0x066167C63111D8CF` the exact signature
`(speed, respectHorizontalOffset, horizontalOffset, respectDistance, distance)`.
Those are the only continuous third-person position arguments available to a
script. The CAMERA namespace does not expose a continuous vertical/pivot-height
argument or a getter for the current orbit distance.

The earlier audit missed `0x71D71E08A7ED5BD7`. Its known behavior is to move
third-person framing closer to ground level while called each frame; it accepts
only a `BOOL`. Rockstar's own `main.c` and camp scripts call it every frame in
their relevant states. This is a real vertical/framing choice, but only
LOW/NORMAL, not a numeric Y axis. A continuous Y/height slider would therefore
be dishonest and was not added.

`0xA24C1D341C6E0D53(1,0,0)` is used by shipped Story scripts to test ordinary
first person. `IS_FIRST_PERSON_AIM_CAM_ACTIVE` covers the aim case. Both are
excluded so third-person calibration never writes over first person.

## Implementation

Added the issue-owned `modules/gameplay_camera.cpp` replacement module. It has
separate standing, crouched, prone, horseback, vehicle and aim profiles. Aim has
precedence over the underlying on-foot/mounted/vehicle state so its profile is
consistent. Scripted/cinematic, mission and first-person cameras remain alone.

The currently active real mode is calibrated directly:

- Numpad 4/6: signed horizontal/shoulder offset.
- Numpad 8/2: orbit distance.
- Numpad 7: real LOW/NORMAL ground-level framing toggle.
- Shift: fine increments for the two continuous controls.
- Numpad 5: persist all six profiles to `[Camera]`.

The existing on-foot zoom-lock option is retained only for standing, crouched
and prone modes. It is not forced onto aim, horseback, or vehicle cameras.

## Integration handoff

The integration owner must include `modules/gameplay_camera.cpp`, replace the
old `updateGameplayCamera(...)` dispatcher call with
`updateGameplayCameraEditor(...)`, and remove the superseded camera globals,
config reads, and old function from `script.cpp` / `world_economy.cpp`. Feature
agents do not edit those integration/shared files or build/install the ASI.

## Static verification

`python tools/reverse-engineering/verify_gameplay_camera_issue_8.py` checks all
six modes, real native hashes, first-person exclusions, controls, persistence,
and the absence of fake numeric vertical keys.

In-game acceptance remains required for each third-person mode, especially
whether the shared gameplay-camera parameter native affects the mounted,
vehicle, and aim camera rigs exactly as its general third-person contract says.

The follow-up increased held-key calibration from one 0.02 step every 60 ms to
one 0.05 step every 16 ms, while Shift retains the 0.005 fine step. The native
surface still exposes no continuous Y scalar: vertical framing is the genuine
binary LOW/NORMAL control, not a hidden or omitted numeric setting.

The next report identified two workflow defects. Calibration was still gated by
a separate `CalibrationMode` setting even though development mode already owns
developer-only overlays; that setting was removed and calibration now follows
`developmentModeActive()` directly. The camera parameter native was also
reasserting the same signed horizontal offset every frame, fighting Rockstar's
keyboard/gamepad `INPUT_SWITCH_SHOULDER` behavior and producing progressively
smaller movements. The module now observes that action's real edge and reverses
the complete applied offset without changing the saved profile calibration.

## Current actionable pass

The authored default blend speed was reduced from 10 to 1 so an adjustment
interpolates instead of appearing as a teleport. Camera settings are now loaded
by the shared two-second config refresh, so saved INI edits apply live. The
development build exposes the calibration overlay without a separate gate, and
its numpad handler yields while the fortification calibrator owns those keys.
The camera verifier passes.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-10 keypad-ownership correction

The returned test showed the camera editor absent: keypad input and the tilde
development toggle appeared to do nothing. The shared ownership flag could be
left on the gold-core calibrator while that calibrator returned before reading
Numpad 0 (hidden HUD, unavailable reference canvas, or a texture dictionary
still loading). The camera editor then yielded every keypad frame to an editor
that was neither drawing nor accepting the exit key.

`gameplay_camera.cpp` now observes the gold editor's Numpad-0 result and flips
the shared flag itself only when the earlier updater did not. With development
mode on, the camera editor is the default keypad owner; Numpad 0 swaps to the
gold-core editor and the next press swaps directly back. Tilde remains the
development-mode on/off control. The #8 static verifier covers the swap and the
stuck-owner recovery. No build, install, runtime claim, or label change was made
in this issue-local pass.

## 2026-08-10 returned-test correction — release build made editor unreachable

The combined installed build
`E3CADC51EEAD96B3A45958ECBE41E99A29F376944B9C28E92ABB88717E7235AA`
produced no camera-editor overlay or keypad response. The installed
`GameplayTweaks.log` gave the exact cause on its first line:
`[core] session start build=release`. `developmentModeActive()` is defined as
the compile-time `GameplayTweaksBuild::Development` flag AND the runtime toggle,
and the tilde handler itself is inside `#if GAMEPLAYTWEAKS_DEV_MODE`. In that
installed ASI, the camera dispatcher ran (the watchdog repeatedly reached
`updateGameplayCameraEditor`) but no key could ever make calibration active.

The module now emits a `camera-editor` session record and three-second heartbeat
with compile mode, runtime development state, keypad owner, mission/cinematic/
gameplay/first-person gates and the final active/inactive editor state. A
physical tilde edge in a release build explicitly logs
`blocked=release-build`; Numpad 0 logs whether the fortification updater or the
camera fallback performed the ownership swap. This preserves the required
compile-time authoring safety boundary and makes another wrong-build install
immediately diagnosable instead of silently AWOL.

### Integration requirement

The integration owner must compile this returned #8 pass with
`GameplayTweaks/build-dev.bat`, then verify the installed log says both
`[core] session start build=development` and
`[camera-editor] ... build=development runtimeDev=1 ... editor=active` before
moving #8 to `test me`. A normal `build.bat` artifact cannot satisfy this issue's
explicit development-only editor acceptance test.

`python tools/reverse-engineering/verify_gameplay_camera_issue_8.py` passed.
No shared build/dispatcher/INI/manifest file, installation or label was changed
in this feature repair. Runtime acceptance still requires visible tilde toggle,
camera-owned keypad adjustment, Numpad-0 transfer to the fortification editor
and transfer back.
## 2026-08-10 release-editor correction

The installed release artifact proved the camera editor was unreachable because
its calibration path inherited the global developer-mode gate. Requiring a
global development build would also expose unrelated F2/F3 authoring tools, so
integration rejected that boundary. `gameplay_camera.cpp` instead gained a
release-only tilde latch owned solely by the camera editor. Development builds
still follow the global developer-mode latch; release builds can calibrate the
camera without enabling any other development-only command. The heartbeat now
reports the resulting camera-editor state in both build modes.
## 2026-08-10 combined release

- Release ASI built successfully: `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`.
- RDR2 was running, so one hidden payload-only installer was queued. The issue remained actionable pending game-root hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.

## 2026-08-10 shared developer-mode semantics repair

- Removed the camera module's private release-only tilde latch. The camera
  editor no longer reads `VK_OEM_3`, toggles any mode, or decides behavior from
  the compiler build flag. Its sole authoring gate is now the shared
  `developmentModeActive()` predicate.
- Camera calibration, keypad ownership, and profile saves remain unreachable
  while that predicate is false. The ordinary gameplay-camera profile natives
  continue independently; disabling developer mode disables authoring, not the
  player's configured camera.
- The camera log now records the shared developer-mode state when first
  observed and whenever it changes. Its existing three-second heartbeat and
  Numpad-0 ownership records remain the execution proof.

### Exact integration requirements

The integration owner must make the shared runtime boundary match the latest
request without turning authoring keys into normal-player inputs:

1. Initialize `g_runtimeDevelopmentMode` to `false` in every build and make
   `developmentModeActive()` return that runtime state without ANDing it with
   `GameplayTweaksBuild::Development`.
2. Compile the one tilde edge handler into the normal build. It alone toggles
   the shared state, reloads gated settings, emits the enable/disable feed, and
   logs the resulting state.
3. Compile the existing F2 collectible relocation and F3 campsite authoring
   paths, but retain their explicit `developmentModeActive()` conditions. Do
   not remove those runtime predicates.
4. Gate `VisibleGoldOverfill::updateCalibration` itself on
   `developmentModeActive()`. Its current Numpad-0 handler is not runtime-gated;
   merely resetting ownership later in the camera update would still allow a
   one-frame authoring input while developer mode is off.
5. Re-audit every raw authoring key after the change. Tilde-off must leave F2,
   F3, camera numpad controls, and fortification numpad controls inert; tilde-on
   makes those same existing tools reachable. Do not make diagnostic settings
   enabled by default merely because their code is compiled.

The issue-local camera verifier passes and reports these shared integration
gaps until the integration owner completes them. No shared file, build,
installation, or label was changed in this pass.

## 2026-08-11 actionable swarm audit

The current shared dispatcher still does not satisfy the live developer-mode
request. `script.cpp` initializes `g_runtimeDevelopmentMode` from the compiler
build flag and compiles the tilde handler only inside
`#if GAMEPLAYTWEAKS_DEV_MODE`. Therefore a release build cannot turn the editor
on, while a development build starts it on instead of requiring tilde. The
camera module itself correctly reads only `developmentModeActive()`; this issue
pass did not edit the integration-owned dispatcher.

The old `-2..+2` horizontal limit had already been replaced by another
unsupported `-20..+20` limit. Both values were project inventions. The camera
module now rejects only non-finite input and does not impose an upper bound.
Negative values are normalized to a magnitude because the two live shoulder
tests showed that a negative value did not create the opposite shoulder.

The camera now also has distinct `Armed` and `CrouchedArmed` profiles for the
Rockstar follow-camera state reported in #177. Integration must add their INI
keys plus `ModeDwellMs` and `SampleIntervalMs`; no shared INI was edited here.

Static verification is not player-visible acceptance. Integration must repair
the one shared tilde boundary, compile, install, and then confirm: tilde starts
off and toggles all authoring tools; Numpad 0 transfers editor ownership; large
horizontal values remain editable; and each live camera profile is selected
without a jump.

## 2026-08-10 ignored requirement and returned runtime failure

The issue was incorrectly moved from `actionable` to `test me` after Lexer had
already added the crouched-aim requirement. That comment was not answered or
implemented before the label transition. The live issue has been returned to
`actionable`; it must not move again until this repair is compiled and actually
installed.

The later runtime report identifies four coupled defects in the installed
camera state model:

1. `Aim` won before stance selection, so crouched aim used `AimLowCamera=0` and
   the module explicitly forced NORMAL framing every frame. A distinct
   `CrouchedAim` profile now defaults to Rockstar's real LOW framing. This does
   not invent continuous vertical positioning: the resolved native remains a
   binary LOW/NORMAL switch, which is also how the requested lower crouch-aim
   presentation is expressed.
2. Aim entry stopped the on-foot close-step force, allowing Rockstar's stored
   third-person zoom step to appear briefly before the configured aim distance
   blended back. Both standing and crouched aim now retain the same configured
   close-step lock, removing that far-then-near transition.
3. The module observed shoulder input but allowed Rockstar to process the same
   input underneath its every-frame horizontal override. It now disables only
   `INPUT_SWITCH_SHOULDER`, reads the disabled edge itself, and flips the whole
   configured offset. Because the module owns the action, this also works with
   no weapon drawn.
4. The +/-2 horizontal clamp had no primary-source basis. It is replaced by a
   broad +/-20 corruption guard; the runtime native remains the authority on
   its actual usable range.

Runtime acceptance must cover independent standing-aim/crouched-aim values,
stable lower crouch-aim height with no bobbing, no far-distance flash on aim
entry, full left/right shoulder placement with and without a drawn weapon, and
continued live numpad calibration/persistence.

## Recurrence audit — #8/#154 coupled shoulder pass

- **Primary evidence/reference:** the live #8 body and every owner comment define
  the seven camera profiles, shared tilde developer-mode boundary, unrestricted
  useful horizontal calibration, stable crouched aim, and full shoulder swap.
  Live #154 is the explicit unresolved acceptance: shoulder switch still does
  nothing while Arthur's gun is holstered. The resolved PAD control definition,
  the current module, and opened Story call sites are required before changing
  input ownership; prior comments and native-call intent are not proof.
- **Sanctioned path:** consume the resolved shoulder action on its rising edge
  and change only the camera module's applied side state. Do not require a drawn
  weapon unless authoritative Story evidence proves the gameplay-camera native
  itself has that restriction. Preserve shared developer-mode/keypad ownership;
  shoulder switching is gameplay behavior and must not be gated by editor mode.
- **Execution proof:** bounded camera logging must distinguish raw/disabled
  shoulder edge, holstered versus armed state, selected profile, old/new side,
  and the value actually submitted to the gameplay-camera native. An attempted
  native call or an editor heartbeat alone is not a visible result.
- **Rendered/player-visible acceptance:** with developer mode both off and on,
  shoulder switch must visibly move fully between sides while holstered and
  armed, without centering, double-processing, teleporting, horizontal clamp,
  aim-distance flash, or crouched-aim bob. Static/native readback remains
  insufficient; this must be seen in Story gameplay.
- **Per-frame mutation:** the resolved camera natives may be asserted only in
  their documented frame-scoped active-camera path. Shoulder side changes and
  persistence are rising-edge/explicit-save operations; no per-frame weapon,
  task, holster, or unrelated camera-state mutation is authorized.

## #8/#154 holstered-input repair

The visible failure was upstream of the camera setter: the module listened only
for the contextual `INPUT_SWITCH_SHOULDER` disabled-control edge. The installed
log contained camera heartbeats but no shoulder-edge record, matching Lexer's
report that physical X did nothing while holstered. Rockstar's extracted
control data confirms the semantic action is contextual and maps its controller
source to `PAD_LLEFT`
(`_downloads/extract/update_1_common/common/data/control/common/common.meta:515-523`);
`settings.meta:3766-3769` also shows that D-pad-left shares Player Menu and Open
Journal, so globally consuming raw D-pad-left while holstered would break
unrelated controller behavior and was not added.

The camera module now retains the remappable semantic action when Rockstar
activates it and adds one explicit rising-edge fallback for the physical X key
Lexer reported. The two sources are combined before a single side reversal, so
an armed press cannot double-flip when both are visible. The fallback is gated
by `PLAYER::IS_PLAYER_CONTROL_ON`; holding X through a pause/menu state cannot
produce a delayed swap. `DISABLE_CONTROL_ACTION` now passes `FALSE`, matching
opened Story call sites (`binoculars.c:406`, `camera_item.c:966`) and avoiding
suppression of related D-pad-left actions.

Each edge now records source, active profile, aim-held state, current weapon
hash, whether the resolved holster state is currently transitioning, old/new
side, and the exact signed horizontal value submitted that frame. The module
does not draw/holster a weapon or mutate ped tasks. The camera native remains
`_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` (`0x066167C63111D8CF`), whose documented
arguments are general third-person horizontal offset/distance and contain no
weapon-state parameter (`_downloads/natives.json:10151-10177`).

Static verification proves the input path and single submission, not the
rendered result. Story acceptance still requires visibly observing full swaps
while holstered and armed, in both standing and aim profiles, plus the existing
crouched-aim/zoom/editor checks from the live #8 body.
