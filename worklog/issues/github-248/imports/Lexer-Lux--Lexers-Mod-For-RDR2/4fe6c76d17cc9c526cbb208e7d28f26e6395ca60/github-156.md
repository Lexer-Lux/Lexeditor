# Worklog: GitHub issue 156

## 2026-08-10 recurrence audit before source edits

### Primary evidence / reference

- The complete live issue says: "You never got rid of crouch running." It has
  no comments. This is the player-visible result and overrides prior static
  claims that a crouch blend ceiling was sufficient.
- The current installed unified log reports only
  `[human-movement] idle enabled=0 ... frames=0`. The current clean process
  therefore provides no execution evidence for the repaired source path; it
  neither proves nor disproves that source when enabled.
- `fuckups.txt` requires an executed path and a readable postcondition. A
  disabled heartbeat is proof of non-execution, not proof that crouch running
  was fixed.

### Sanctioned path and shared owner

`human_movement.cpp` is the single ordinary on-foot gait owner for #144, #156
and #157. Crouch/stealth must take precedence over Shift, consume Rockstar's
Sprint action for that frame, and constrain the graph to its crouch-walk band
without forcing motion state, desired blend, min=max pinning, task animations,
velocity or teleport. `movement.cpp` remains owner only for #6 roll, #9 prone
and #97 climbing; the human gait module yields to those states.

### Actual execution / postcondition

The enabled trace must show `sneak=1`, Sprint held/blocked state, selected gait,
maximum blend ceiling, desired-blend readback, `IS_PED_RUNNING`,
`IS_PED_SPRINTING`, and entity speed. Holding Shift while crouched counts only
when consecutive moving readbacks show neither run nor sprint and stay inside
the proven crouch-walk blend band. Setter calls alone are not success.

### Player-visible acceptance

From standing and while already crouched, hold Shift and move in all directions.
Arthur must remain in smooth crouch-walk with no crouch run/sprint, accelerated
animation, skating, stand transition or Stamina sprint classification. Releasing
and pressing Shift repeatedly must not latch a faster crouch gait. #6 roll and
#9 prone must still take ownership and restore ordinary gait cleanly.

### Every issue-owned per-frame native

The replacement may read movement input, sprint input, crouch/stealth state,
run/sprint state, desired blend and entity speed each owned frame. The only
allowed active-frame gait writes are the frame-scoped move-rate scalar, a true
maximum-blend ceiling with minimum left at zero, and Sprint control suppression
while crouched/non-sprinting. `FORCE_PED_MOTION_STATE`, desired-blend writes,
minimum-blend writes, min=max pinning, animation tasks and velocity writes are
forbidden. Default restoration writes occur only on ownership/yield edges.

## Issue-local shared-gait implementation

`human_movement.cpp` remains the only ordinary on-foot gait writer. The crouch
branch already preceded sprint and used Rockstar's repeatedly shipped
`SET_PED_MAX_MOVE_BLEND_RATIO(Global_35, 1f)` mechanism; this pass makes its
ownership and failure observable rather than accepting setters as success:

- `sprintAllowed` is false for every crouch/stealth frame, including held Shift;
- Sprint is disabled before the active-frame rate and 1.0 maximum ceiling are
  written;
- consecutive crouched moving frames now read actual run, actual sprint,
  desired blend and speed;
- a rejected crouch-walk postcondition emits a 250 ms bounded warning with
  physical Shift and Sprint-block state;
- the five-second heartbeat includes Sprint-block state and the consecutive
  crouch-walk confirmation count.

No motion-state, desired/minimum blend, animation-task, velocity or teleport
write was added. The first failed #144 engine fight remains removed.

Added `tools/reverse-engineering/verify_human_movement_issue_156.py`. It checks
Rockstar's 1.0 ceiling in `act_caunc_rustling.c`, crouch-before-sprint branch
ordering, input suppression, live no-run readbacks and the forbidden writer
set. It passes together with #144, #157, #6 and the 34-invariant #9/prone/climb
suite.

The installed `[HumanMovement] Enabled=0` state was not edited, so this source
has not executed in game. Integration must deliberately enable the shared gait
feature in a new build/test configuration after a clean restart; only the
player-visible crouch/Shift test in the recurrence audit can accept #156.
