# GitHub #160 - angled-surface mantle handoff

## Recurrence audit before source repair

### Primary evidence

- The live report is exact: on a roughly 45-degree house roof, Arthur left
  climb mode instead of mantling, fell, and was then teleported onto the roof.
- Current source reproduces that sequence structurally. It clears the custom
  task and releases kinematic ownership before calling `TASK_CLIMB`; if native
  climbing/vaulting is not observed for 1200 ms, it calls
  `SET_COORDS_NO_OFFSET(ped, g_climbTopOutTarget)`. That is the reported fall
  followed by delayed roof teleport, not an inference.
- `_downloads/natives.json` resolves `TASK_CLIMB` as "Climbs or vaults the
  nearest thing." `marston4.c:55369-55378` uses `TASK_CLIMB(..., false)` in
  Story traversal sequences. `GET_SCRIPT_TASK_STATUS` is resolved in
  `natives.h:7114-7116`; `joaat("SCRIPT_TASK_CLIMB")` is `-1207763510`, the
  exact hash queried after one-shot `TASK_CLIMB` in
  `feud1.c:59576-59585` and `59684-59693`.

### Sanctioned path and execution proof

The verified lip remains custom-owned only while the one-shot native mantle is
pending. Release custom physics only after live `IS_PED_CLIMBING` /
`IS_PED_VAULTING`, or task status `1` (`PERFORMING_TASK` in natives.json),
confirms native acceptance. If the task is rejected, cancel it and return to
the attached idle grip at the same lip; never fall for 1.2 seconds and never
teleport to the landing. Log task status, native traversal, ownership and age
during the bounded handoff.

### Player-visible acceptance

On a flat ledge and a roughly 45-degree roof, pushing up at the verified lip
must either enter Rockstar's visible mantle and land naturally or remain
attached at the lip. Arthur must not visibly leave climb mode before the native
mantle owns him, fall, clip through the lip, receive a delayed coordinate snap,
or acquire launch velocity.

### Per-frame native inventory

`TASK_CLIMB` is issued once per verified top-out attempt. While native
acceptance is pending, the existing custom climb owner retains its ordinary
coordinate and zero-velocity writes for a bounded 350 ms; it does not force an
animation state. `GET_SCRIPT_TASK_STATUS`, `IS_PED_CLIMBING`, and
`IS_PED_VAULTING` are readbacks. The delayed top-out coordinate fallback is
forbidden.

## Implemented repair and static result

The top-out issuance no longer calls `releaseClimbPhysics`. It clears the
outgoing custom animation, issues `TASK_CLIMB` once, and retains the verified
lip during a 350 ms acceptance window. Status `1` or a live climb/vault flag
hands ownership to Rockstar. Rejection clears the task and returns directly to
the attached Climbing state; up input must be released before another attempt.
Completion is the live traversal ending or status `8` (`FINISHED_TASK`). A
five-second accepted-task stall yields at the live position. The old
`SET_COORDS_NO_OFFSET(...g_climbTopOutTarget)` delayed fallback is gone.

`verify_climbing_issue_160.py` passes, as do #97 and adjacent parity checks.
Runtime still must prove an actual visible native mantle on both a flat lip and
the reported angled roof; rejection remaining safely attached is the explicit
non-destructive boundary, not a claim that every roof is natively mantleable.

## 2026-08-10 live rejected-mantle correction

The trace showed the angled mantle request enter task status 1 and then status
8 without `nativeTraversal`. The code correctly kept physics ownership, but it
returned to the ordinary climbing loop while Up was still held. That loop moved
the owned anchor above the last real lip, which matches Arthur grabbing open air
and then falling.

After a rejected mantle, all climb input is now treated as Idle until Up is
released. The verified lip remains pinned and the idle grip owns the pose. No
new mantle retry or coordinate snap can occur during the same held input.
