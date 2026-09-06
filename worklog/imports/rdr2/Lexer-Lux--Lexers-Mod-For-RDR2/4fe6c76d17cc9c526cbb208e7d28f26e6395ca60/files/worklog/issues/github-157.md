# Worklog: GitHub issue 157

## 2026-08-10 recurrence audit before source edits

### Primary evidence / reference

- The complete live issue reports that releasing held Run/Sprint returns to
  vanilla running instead of walking. It has no comments. The required
  transition is therefore held Shift = sprint, release Shift = direct walk,
  with no intermediate or latched run.
- The current installed unified log contains only disabled
  `[human-movement]` heartbeats with `frames=0`. No enabled release edge or
  walk postcondition ran in that process. Prior source/verifier claims are not
  runtime acceptance.
- The first #144 controller's per-frame forced motion state plus collapsed
  min=max=desired blend is a documented catastrophic engine fight. The fix may
  not reintroduce any part of that combination to hide vanilla run.

### Sanctioned path and shared owner

`human_movement.cpp` alone owns ordinary walk/sprint semantics. Rockstar keeps
its natural sprint animation while Shift is held; on the physical/action
release edge the module suppresses Sprint and applies only the walk maximum-
blend ceiling plus configured rate scalar. It must yield to #6 roll, #9 prone,
#97 climbing, mounts, water, falls/ragdoll, menus and cutscenes, restoring
defaults once on the yield edge. No second gait writer belongs in
`movement.cpp`.

### Actual execution / postcondition

The trace must distinguish Shift/action held, release edge, control suppression,
selected gait, maximum ceiling, actual run, actual sprint, desired blend and
speed. The release is accepted only after consecutive moving-frame readbacks
show no run, no sprint and walk-band desired blend. The first moving frame
after release is separately recorded so an intermediate vanilla run cannot be
hidden by eventual convergence.

### Player-visible acceptance

Walk without Shift, hold Shift to transition naturally to sprint, then release
while continuing forward/diagonal movement. Arthur must return directly and
smoothly to walk on that release, never jog/run for an intervening frame, never
retain a toggle latch, and never stutter, accelerate animation or skate. Repeat
while aiming and after #6/#9/#97 ownership returns. Stamina must immediately
classify the post-release gait as walking, not jogging.

### Every issue-owned per-frame native

Owned-frame reads may observe movement/sprint input, crouch, run/sprint,
desired blend and speed. Active-frame writes are limited to the frame-scoped
move-rate scalar, non-collapsed maximum-blend ceiling and conditional Sprint
control suppression. Forced motion state, desired/minimum blend, task/velocity
writes and unconditional default restoration are forbidden. Release diagnostics
are state-edge/readback records, not extra locomotion mutations.

## Issue-local shared-gait implementation

The old source selected walk on release but did not keep that state exclusive:
if Shift was re-observed before the three-frame postcondition settled, its
sprint branch could reopen while `releasePending` was still true. The shared
controller now defines `sprintAllowed` as held Shift only when not crouched and
not inside the release-confirmation window. On the release edge it therefore:

1. keeps Rockstar's Sprint action disabled;
2. selects the walk branch and 1.0 maximum blend ceiling in the same owned
   update;
3. records the first owned-frame run/sprint/blend/speed readback;
4. keeps walk ownership until three consecutive moving frames report no run,
   no sprint and desired blend no higher than 1.05 (numeric tolerance around
   the written 1.0 ceiling).

Only after that postcondition may a later held Shift enter Rockstar's natural
sprint branch. No forced motion state, desired/minimum blend, task animation,
velocity or teleport mechanism returned.

Added `tools/reverse-engineering/verify_human_movement_issue_157.py`. It checks
release/suppression/ceiling/readback ordering, the pending-release sprint gate,
first-frame diagnostic, three-frame postcondition and forbidden writer set.
It passes together with #144, #156, #6 and the 34-invariant #9/prone/climb
suite.

The shared INI remains safely `Enabled=0` and was outside this issue-owned
scope. A new integrated test must deliberately enable the module after a clean
restart. Runtime acceptance requires the very first continuing-movement frame
after Shift release to show no visible intermediate run and the subsequent
three-frame trace to confirm walk; eventual convergence alone is not enough.
