# Worklog: Todo 170

## #170 prone sinking — fixed, BUILT BUT NOT INSTALLED 2026-08-05

Cause: the terrain-alignment block writes SET_ENTITY_ROTATION(pitch, roll,
heading) every frame to lay him along the slope, and NOTHING corrects Z.
Rotating the root tips the collision capsule so part of it ends up below the
surface; the solver resolves the interpenetration by displacing him, and that
displacement is what ends the prone state and stands him up. The sink and the
bounce are one event, not two bugs. This is the same failure releaseClimbPhysics
already documents ("the solver resolve the interpenetration by ejecting him
through the world") - there it is fixed by snapping to valid GROUND_Z first;
prone never had any Z handling at all.

FIX: a floor CLAMP after the alignment block - sample GROUND_Z under the root,
reject samples more than 2.5 m away (cliff edge / roof below), and only when he
is more than 2 cm BELOW groundZ + clearance, SET_COORDS_NO_OFFSET to that height
and zero any downward velocity. Deliberately a clamp and not a position drive,
so the crawl velocity still owns x/y and normal terrain following is untouched.
New `[Prone] FloorClamp` (default 1) and `GroundClearanceMeters` (default 0.05).

Built exit 0, sha256 begins 8e5ee8e25a684727.

NOT INSTALLED. RDR2 was running when the copy was attempted and the .asi is
locked by the process. The build loaded in Lexer's live session is the previous
one, 1d1f4a1eb5b8ccd9, which contains all twelve requested items plus the
plants-only filter but NOT this prone fix. Install on the next game-closed
window and re-verify the hash.


## #170 prone — four defects fixed from live-log evidence, 2026-08-04

Build `4168210BAE0808C2AC95BB4285337EB0B231CAFD06340FC9FD1A6AFA8621BA76`,
installed and hash-verified against the game root while RDR2 was running (the
loaded image was renamed to `GameplayTweaks.asi.loaded.20260804-040322`). INI
synchronized, both copies hash-equal. Needs a full restart: ASI change.

Evidence used, not guesses: `GameplayTweaks.prone.log`, current session block at
tick 423936343+. Note the earlier `binocular roll to back` lines at 74883796 are
from a PREVIOUS build/session — `customBackRigEnabled` is still false.

- Stand-exit double getup. `beginProneExit` called `CLEAR_PED_TASKS` before
  issuing the exit clip, so the ped rendered its standing base pose in the gap
  before the clip bound; then it played
  `ai_getup@directional_sweep@combat@cop@rifle@front/get_up_0` — a rifle combat
  recovery — for EVERY weapon including unarmed. Both halves match the report
  exactly. Fix: no task clear (TASK_PLAY_ANIM already replaces the running crawl
  task; the idle<->walk switcher has always relied on that and never clears), and
  use `proneGetupDict()` + `mech_weapons_core@base@dive@{unarmed,pistol,rifle}@getup`
  / `dive_getup_fwd`, which had been defined, registered for streaming, and never
  called since it was written. Combat sweep retained as the not-streamed fallback.
  Also removed the early `applyCrouchStance(ped,false,true)`: `finishProneExit`
  already does it at the end of the clip, and doing it up front let the engine
  stand him underneath the animation.
- Wheel slide (reports b and d). `INPUT_OPEN_WHEEL_MENU` does not read as a
  continuous press: the log shows `wheel close` at 424128015/424129843/424131234
  for one selection. Each bounce hit `if (wheelOpen) { g_proneLocoClip = nullptr;
  return; }`, which only FORGOT the running clip — `walk`/`walk_turn_r4` kept
  playing with root motion while the early return skipped both steering and the
  velocity pin. `walk_turn_r4` is the "sliding right super fast" case; the wheel
  also reuses the movement axes for selection, feeding it. Fix: latch the wheel
  open for `WheelGraceMs` (250) past the last pressed frame, force the no-root-
  motion `idle` clip, and pin horizontal velocity.
- Weapon never drawn. `SET_CURRENT_PED_WEAPON` was committed but crawl reclaimed
  the skeleton the next frame, so the draw had nowhere to play; `g_proneEquipUntil`
  was being set to 0, disabling the window that existed for this. Fix: clear tasks
  once at wheel close and hold for `EquipHoldMs` (700), velocity pinned, then
  resume crawl idle.
- Binoculars stood him up. Root cause was NOT in updateProne — the binocular
  hold handler itself ran `CLEAR_PED_TASKS` on `g_proneTaskOwnsSkeleton` the
  moment the hold threshold passed, dropping crawl before the prone system saw
  the request. Fix: new `proneRequestStandForNativeAction(ped, reason)`
  (forward-declared above the binocular code) gates it. `BinocularMode=1`
  (default) runs the authored `prone_to_knees@crawl/front` exit first;
  `BinocularMode=0` refuses. There is no authored prone binocular animation in
  the game; the on-back pistol rig remains the only real answer and is still
  disabled for rolling through terrain when timer-driven.

Build note: `AGENTS.md`'s documented compile line omitted `user32.lib xinput.lib`
and fails with six unresolved externals. `GameplayTweaks/build.bat` is correct and
AGENTS.md has been corrected to point at it.

