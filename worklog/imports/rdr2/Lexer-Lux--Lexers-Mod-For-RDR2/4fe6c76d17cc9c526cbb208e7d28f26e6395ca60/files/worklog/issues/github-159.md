# GitHub #159 - stop climbing animation on input release

## Recurrence audit before source repair

### Primary evidence

- The live issue title is the full current report: Arthur continues the
  climbing animation after the movement control is released. #97's latest live
  comment independently repeats the same failure.
- The current installed INI has `[Climbing] DevelopmentTrace=1`, but the latest
  unified `GameplayTweaks.log` contains no `climbing` records. That session did
  not execute an observable climb, so it cannot be cited as a negative result.
- Current source identifies the concrete semantic defect. On a moving-to-idle
  edge it calls `_SET_ENTITY_ANIM_SPEED(..., 0.0f)`. That pauses the outgoing
  task on its current pose; it does not stop or blend out the task. The existing
  #97 verifier only looked for that call and therefore certified the defect.
- `_downloads/RDR2_SDK/SDK/inc/natives.h:7060` resolves
  `TASK::STOP_ANIM_TASK` to `0x97FF36A1D40EA00A`. Decompiled Story scripts use
  it to end a named running animation, including
  `beat_del_lobo_posse.c:10124-10140` and
  `beat_kidnap_victim.c:6332-6334`.

### Sanctioned path and execution proof

On the single input transition from Up/Down/Left/Right to Idle, stop the exact
outgoing dictionary/clip once with `STOP_ANIM_TASK`, then issue the existing
idle grip. Do not clear all tasks or reissue the stop every frame. A bounded
readback must record whether the outgoing clip is still playing and whether the
idle grip has bound/progressed; a stop call alone is not success.

### Player-visible acceptance

Releasing W/S/A/D while attached must stop traversal and its moving animation
without an extra reach, a frozen mid-stride pose, continued movement, task
clear/A-pose, or a delayed idle transition. Re-pressing a direction must start
normally. Keyboard and controller release require the same result.

### Per-frame native inventory

No new per-frame write is permitted. `STOP_ANIM_TASK` is release-edge-only.
Existing coordinate/zero-velocity writes remain limited to the already-owned
climb state. Animation readbacks run only during the bounded release audit.

## Implemented repair and static result

The moving-to-idle transition now lives outside the animation-dictionary load
gate, so it cannot be skipped if streaming state changes. It calls
`STOP_ANIM_TASK` once for the exact outgoing dictionary/clip, selects the
existing idle grip, and at 180 ms records `outgoingPlaying`, `idleSelected`,
idle phase and zero anchor speed. The old animation-speed-zero pause was
removed from both vertical and lateral release paths.

`verify_climbing_issue_159.py` passes. Adjacent #97, 34-invariant prone/climb
parity, #6, #144, #156 and #157 checks also pass. This is static/authoritative
path evidence only; player-visible release timing remains an in-game boundary.

## 2026-08-10 live release retry

The current log caught the intermittent failure. One release stopped the exact
clip and selected idle, but another still reported `outgoingPlaying=1` and
`idleSelected=0` after 180 ms. The audit previously logged that failure and then
forgot it. It now retains the failed postcondition and retries the same exact
named task at most twice with a faster blend-out. Each retry is logged; no task
tree clear or indefinite per-frame stop was added.
