# GitHub #82 - Holster Key Should Actually Holster

## Requirement

Pressing the holster key with a rifle in hand must play the ordinary put-away
animation seen when selecting hands in the weapon wheel. It must not teleport
the rifle directly onto Arthur's back.

## Cause

The existing fallback recognized `INPUT_TOGGLE_HOLSTER`, but its final action
used `_HIDE_PED_WEAPONS(..., true)` and
`SET_CURRENT_PED_WEAPON(..., WEAPON_UNARMED, true, ...)`. Those `true` arguments
request immediate/forced state changes. The fallback also omitted the weapon
swap task. That combination changed the attach state instantly instead of
asking the task system to animate the stow.

## Shipped-script evidence

`_downloads/RDR2-Decompiled-Scripts/script_rel/act_bankrobbery01.c`, function
`func_586`, contains Rockstar's complete ordinary put-away sequence:

1. `_HIDE_PED_WEAPONS(ped, 2, false)`
2. `SET_CURRENT_PED_WEAPON(ped, WEAPON_UNARMED, false, attachPoint, false, false)`
3. `TASK_SWAP_WEAPON(ped, 0, 0, 0, 0)`

The same sequence appears in `act_caunc_rustling.c`, function `func_1251`, when
an armed ped mirrors an unarmed player. The SDK defines `TASK_SWAP_WEAPON` as
native `0xA21C51255B205245`; Rockstar's task-status checks identify its script
task hash as `716706914`.

## Implementation

`GameplayTweaks/modules/world_economy.cpp` now uses that exact non-immediate,
non-forced three-call sequence after the existing input and in-hand gates. The
draw path remains untouched: if attach point 0 is empty/unarmed, the function
returns and lets the game's normal Tab behavior run.

## Static verification

- Confirmed the old immediate/forced pair no longer exists in the holster path.
- Confirmed the replacement call sequence and parameters match both decompiled
  examples above.
- Confirmed `TASK::TASK_SWAP_WEAPON(Ped, Any, Any, Any, Any)` exists in the
  checked-in SDK header.
- No build, install, game launch, GitHub mutation, commit, or generated-index
  rebuild was performed by the feature agent; those belong to integration.

## In-game acceptance

- With a rifle/repeater/shotgun physically in hand, press Tab and confirm Arthur
  performs the complete normal stow animation before it reaches his back.
- With empty hands, press Tab and confirm the normal draw behavior still works.
- Confirm sidearms still use their normal draw/holster behavior.
- Confirm the feature stays out of the way while mounted, in a vehicle, and in
  missions, as required by its existing gates.

## 2026-08-06 follow-up after failed in-game test

Lexer tested the installed three-call sequence and the rifle still teleported
to his back. The live `GameplayTweaks.holster.log` showed why the prior static
conclusion was incomplete:

```text
before current=4111948705 p0=4111948705 ... p10=2725352035
requested animated stow inHand=4111948705 currentNow=4111948705 p0Now=4111948705
```

The mod's request correctly left the longarm in point 0 while the swap task
began. However, `INPUT_TOGGLE_HOLSTER` remained enabled, so Rockstar's normal
Tab action still ran underneath the scripted task in the same input cycle and
won by attaching the weapon instantly. Matching a mission-script call sequence
was not enough while a competing player control still owned the transition.

The holster path now intercepts rather than competes:

1. When point 0 is empty/unarmed, the module does not disable anything; vanilla
   Tab retains its normal draw behavior.
2. When a weapon is in point 0, the module disables
   `INPUT_TOGGLE_HOLSTER` every frame, detects the press through
   `IS_DISABLED_CONTROL_JUST_PRESSED`, and runs the proven non-forced stow
   sequence without the vanilla action underneath it.
3. If another state had already disabled the control (notably prone or
   binoculars), the module does not reinterpret that locked press.
4. Missions, mounts, and vehicles still return before interception and retain
   their existing behavior.

The request log now includes script task `716706914` status as well as point-0
and current-weapon readback. This distinguishes a task that never started from
one interrupted later by another game state.

Integration boundary: this pass changed only the existing #82 section of
`modules/world_economy.cpp` and this worklog. It did not edit `script.cpp` or
the installer, build/install, mutate GitHub labels, commit, or push.

Runtime acceptance after integration/build/install:

1. Hold a rifle/repeater/shotgun on foot outside a mission and press Tab. The
   full shoulder-to-back stow animation must finish; no instant attach.
2. Confirm the log says `requested animated stow` and reports a non-failed task
   status on the press.
3. Press Tab with empty hands and confirm vanilla draw still works.
4. Confirm sidearm holstering remains animated.
5. Confirm Tab cannot trigger this module while prone/binocular controls lock
   it, and that mounted/vehicle/mission behavior remains vanilla.

## 2026-08-06 correction for repeated presses and hand/back oscillation

The later in-game report was authoritative: one Tab press often did nothing,
repeated taps restarted the request, and the longarm alternated between an
in-hand transition and the vanilla back attachment. The prior interception
still had no ownership state around the asynchronous swap task. As long as
attach point 0 continued to show the rifle, every later physical press issued
the three-call sequence again and could interrupt the transition already in
progress.

Added issue-local `GameplayTweaks/modules/always_holster.cpp` as the replacement
handoff. It:

- accepts one enabled `INPUT_TOGGLE_HOLSTER` edge and disables the competing
  vanilla action;
- issues Rockstar's three-call stow sequence exactly once for that edge;
- holds ownership while script task `716706914` is active and never reissues
  the sequence on a timer or on another tap;
- retries at most once, only on the semantic event that the task ended while
  attach point 0 still contained a weapon;
- waits for both task completion and physical key release before returning to
  idle; and
- leaves empty-hand draw, mounts, vehicles, missions, and prior control locks
  to vanilla/other modules.

Integration must remove the old embedded `updateAlwaysHolster()` from
`world_economy.cpp`, include this module after the globals/wrappers it uses,
and retain the existing call site. This feature pass did not edit the dirty
shared module or dispatcher, compile, link, install, or mutate GitHub.

Static checks confirmed there is no timeout in the replacement and the only
retry is gated by task status plus actual attach-point state. Runtime acceptance
still requires one press each with a rifle, repeater, and shotgun; each must
finish one normal shoulder-to-back animation without a second press or an
intermediate return to the hands.

## Enabled-edge correction

The replacement still disabled `INPUT_TOGGLE_HOLSTER` and only then queried a
disabled-control edge. That ordering can miss the physical Tab edge in the same
frame. The module now samples `IS_CONTROL_JUST_PRESSED` while the control is
still enabled, then disables the competing vanilla action and consumes exactly
that captured edge. Existing ownership and safety gates remain unchanged.

## 2026-08-06 returned-test correction: remove asynchronous retry ownership

The subsequent in-game report proved the enabled-edge correction still did not
work. The live log explained the repeated behavior: the module sampled an
enabled PAD edge before suppressing Rockstar's action, so the native instant
attachment could already consume the same press. The module then waited on task
status and retried, recreating the multiple-press/hand-back oscillation Lexer
explicitly rejected.

The replacement is deliberately smaller:

- while a weapon is in attach point 0, suppress `INPUT_TOGGLE_HOLSTER` before
  querying its disabled edge;
- independently capture the foreground physical `VK_TAB` edge so suppressing
  PAD cannot erase the keyboard press;
- issue Rockstar's non-immediate hide, non-forced unarmed selection, and stow
  task exactly once for that edge; and
- perform no timeout, completion polling, retry, or held-key repetition.

Empty-hand Tab remains untouched for vanilla drawing. Existing mission,
mount/vehicle, and prior-control-lock gates remain. The issue-local verifier
`tools/reverse-engineering/verify_always_holster_issue_82.py` passes and rejects
the removed retry state machine. This is local/static evidence only; it remains
`actionable` until the combined ASI is built and installed.

## 2026-08-06 root cause found: banked key edge + collision with the draw's own swap task

Lexer's own diagnosis was correct and is now located. There IS a post-draw
window in which the stow request cannot succeed, but it was not a timer in this
module — there is no `AlwaysHolsterState`, no ms constant and no retry anywhere
in the previous revision, and grep confirms that. The window came from two
separate defects that compounded.

### Defect A — the physical Tab edge was banked, not drained

`GetAsyncKeyState`'s low bit is a latch, cleared only by a call to
`GetAsyncKeyState` for that key. The previous revision called it at the END of
`updateAlwaysHolster`, behind seven early returns: feature off, no ped, mission,
vehicle, mount, **no weapon in hand**, control already disabled
(old always_holster.cpp:35-42, with the read at line 53).

A weapon is *drawn* by pressing Tab with empty hands, which is exactly the
`!weaponInHand` early return. So every Tab-draw left its edge latched and
undrained. The first frame on which the drawn weapon appeared at attach point 0
harvested that stale edge and issued a stow immediately, inside the running
draw. Every Tab press made while mounted, in a vehicle, in a mission or in a
store banked the same way and fired spuriously on re-entry.

This is the mechanism behind "there seems to be this time period after I pull
out my weapon during which I can't put it away": the press was not being
rejected — it had already been silently spent by the draw itself.

### Defect B — the stow was issued on top of an in-flight weapon-swap task

Draw and stow are the same script task, `716706914`. Rockstar tests it before
every stow; the previous revision did not test it at all.

- `_downloads/RDR2-Decompiled-Scripts/script_rel/act_bankrobbery01.c:22038`
  (`func_586`): `if (!func_226(iParam0, 716706914)) { _HIDE_PED_WEAPONS(...); SET_CURRENT_PED_WEAPON(..., WEAPON_UNARMED, false, 0, false, false); TASK_SWAP_WEAPON(..., 0,0,0,0); }`
- `act_bankrobbery01.c:10854-10866` — `func_226` returns TRUE (busy) when
  `GET_SCRIPT_TASK_STATUS(ped, hash, true)` is `1` or `0`.
- `act_bankrobbery01.c:22057` — status `8` is the finished/none value.
- `act_caunc_rustling.c:13561` — the same `716706914` test before
  `TASK_SWAP_WEAPON`.
- The draw runs through the same task: `act_caunc_rustling.c:26060-26062`
  (`SET_CURRENT_PED_WEAPON(best)` then `TASK_SWAP_WEAPON(ped, 1, 0, 0, 0)`; arg1
  `1` = draw), and `abigail2_1.c:81135`.

### Why the behaviour was non-deterministic

The stale edge from Defect A fired the three-call sequence at an arbitrary point
inside a live draw. Where it landed decided what was seen, which reproduces the
reported tri-state exactly:

- landed early — `SET_CURRENT_PED_WEAPON(UNARMED)` applied, then the draw task
  finished and re-attached: weapon on the back with no animation;
- landed mid — the draw task won outright: weapon ends up in the hand, "like in
  vanilla";
- landed after the draw retired — clean run, the authored stow plays.

Tapping ~50 times eventually placed one tap in the idle window after a draw had
fully retired, which is why brute force appeared to help.

### Not the cause, checked and cleared

- No timeout/retry existed in the tested revision. The "timeout based method"
  was not reintroduced.
- The `IS_CONTROL_ENABLED` guard is not a self-inflicted lockout. The module
  disables the control every armed frame, so a feedback lock was plausible, but
  the feature demonstrably does fire in some frames, which proves the engine
  clears the per-frame disable before the next tick and the read is trustworthy.
- `movement.cpp:1081` (prone) and `combat_inventory.cpp:706` (binoculars) do
  disable `INPUT_TOGGLE_HOLSTER`, but only while those features are engaged.
- `IS_PED_WEAPON_READY_TO_SHOOT` was considered as a second busy signal and
  rejected: `items_casings.cpp:450-461` documents phantom flips and unclear
  semantics for it. It is not used as a gate. Guessing with it would have been
  another unevidenced constant.

### Change

`GameplayTweaks/modules/always_holster.cpp`, rewritten. No timeout, no ms
constant, no retry, no completion poll driving a second attempt, no held-key
repetition. The issue-local verifier still passes and still rejects the old
retry state machine.

- L130-141 — the physical edge is drained **unconditionally on the first lines
  of the function**, before every gate. Deliberately not inside a `&&` so
  short-circuiting cannot skip the read and reintroduce the bank. This alone
  removes Defect A.
- L143-149 — survival readback: the frame after an issue logs task status and
  attach point 0, so an issued-then-killed task is distinguishable from one that
  never started.
- L151-160 — idle heartbeat every 3 s reporting armed/pending/taskStatus, so a
  silent log proves "not running" rather than "nothing happened".
- L162-180 — each gate names itself in the log when it eats a real press
  (`disabled`, `mission`, `vehicle`, `mount`, `emptyHand`, `controlLocked`), and
  clears any latched intent with a reason. Empty-hand keeps its own explicit
  return so the vanilla draw path can never be swallowed.
- L182-204 — one press is latched as one pending intent. Extra taps while an
  intent is pending are coalesced and logged, never queued or reissued; this is
  what stops repeated taps from interrupting the transition they are waiting on.
- L206-220 — the sequence is issued on the first frame `716706914` is not busy
  (status not `0`/`1`), mirroring `func_226`. A press made during a draw now
  waits for the draw to retire and then stows from that single press, instead of
  being spent inside it. The wait is driven purely by task state and ends the
  moment the slot frees.
- L77-86 — the log truncates once per launch instead of appending forever.

Known residual, deliberately not papered over with release-tracking state: the
PAD `IS_DISABLED_CONTROL_JUST_PRESSED` edge can lag the raw keyboard edge by one
frame, so one physical press could in principle be accepted twice. It
self-corrects — the second intent defers behind the first stow's own task and is
then cancelled by the `emptyHand` gate — and both the coalesce and the cancel are
logged, so the runtime log will show whether it ever actually happens.

### Runtime acceptance

1. Draw a longarm with Tab, then press Tab once *immediately*, during the draw.
   Arthur must finish the draw and then play one complete authored stow. No
   second press.
2. Draw, wait for idle, press Tab once. One authored stow, no teleport to the
   back, no return to the hands first.
3. Repeat for rifle, repeater and shotgun, and confirm sidearms still animate.
4. Press Tab with empty hands: vanilla draw unchanged.
5. Press Tab while mounted / in a vehicle / in a mission, then dismount or exit
   with a weapon in hand: nothing must fire spontaneously (this is the banked-edge
   regression test).
6. With `[AlwaysHolster] Log=1`, confirm `GameplayTweaks.holster.log` contains
   heartbeats when idle, and per press one `press accepted`, at most one
   `defer: swap task busy`, one `issue stow`, and one `survived` line.

Static/local evidence only. Nothing built, linked, installed or copied; no
commit, push or GitHub label change. Remains `actionable` until the combined ASI
is built, installed and tested in game.
