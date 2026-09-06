# GitHub #178 - Camera Bobbing When Crouched

## Recurrence audit before source edits

- **Primary evidence:** the live issue reports constant near-sinusoidal camera
  movement whenever Arthur is crouched, independent of LOW/NORMAL. The prior
  camera log could not answer the question: its heartbeat did not record stance,
  submitted values, rendered coordinates, or mode transitions. The latest log
  does show a related classifier problem during aim: raw/applied mode changed
  AIM -> STANDING -> AIM within 141 ms while the two profiles had different
  distances.
- **Sanctioned path:** stabilize profile selection before the documented
  per-frame camera setter. Do not counter-move the camera, freeze it, or invent
  a camera offset.
- **Execution proof:** bounded samples report raw/applied mode, crouch and armed
  state, configured/submitted values, rendered lateral/orbit/vertical position,
  plus raw/applied transition counts. This distinguishes stance flicker from
  engine-owned crouch motion.
- **Player-visible acceptance:** standing still and moving while crouched must
  not pulse between distances or heights. Crouch/stand transitions must remain
  responsive, and LOW/NORMAL must still work.
- **Cadence:** samples are bounded to 10 Hz for crouch-family profiles and 2 Hz
  otherwise. `SampleIntervalMs=0` disables them. No diagnostic writes camera or
  ped state.

## Source result

The applied profile now changes only after the raw profile remains stable for
`ModeDwellMs` (default 100 ms). Raw and applied flip counters show whether this
absorbs a flickering predicate. The read-only camera sample names all state and
coordinates needed for one runtime diagnosis. This is a bounded mitigation and
self-verifying probe, not a claim that the reported crouch bob is fixed: if raw
mode remains stable while rendered coordinates still oscillate, the next repair
must target the engine-side crouch camera rather than increase the dwell.

Integration must add `ModeDwellMs=100` and `SampleIntervalMs=500` to the camera
INI/settings schema, compile, and install. Keep #178 actionable until the log
and visible test establish the postcondition.
