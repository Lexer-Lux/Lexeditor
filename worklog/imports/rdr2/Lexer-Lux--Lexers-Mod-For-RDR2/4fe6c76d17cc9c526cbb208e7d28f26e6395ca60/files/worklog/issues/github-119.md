# GitHub #119 - tiny-rock climbing teleport and animation lock

## Diagnosis

The current climbing fallback defined `carriedDownhill` as any grounded frame
with vertical velocity below -0.30 m/s and horizontal speed above 0.35 m/s.
That is not evidence of a slide: ordinary player-controlled movement down a
small rock or step satisfies it. The fallback then aimed long probes uphill and
down into the terrain. A resolved sloped contact sustained for 140 ms entered
the coordinate-owning `Grabbing` state, whose anchor interpolation pulled
Arthur back to that contact and disabled ordinary movement controls. This
matches the reported small-step trigger, repeated return to the rock, climbing
animation glitch, and apparent input lock.

The installed release build did not emit a trace for this occurrence, so the
specific tick and geometry are unavailable. The trigger is nevertheless a
direct false-positive in the entry predicate: player-controlled downhill
walking was explicitly sufficient to arm `detected_slipping` without Jump,
airborne clearance, backward motion, or Rockstar's slide state.

## Fix

Removed the unconditional `carriedDownhill` predicate. The inferred non-native
slip fallback now requires forward input into the probed face plus observable
failure to make uphill progress (backward movement, or a downward drop while
forward progress is nearly zero). Rockstar's actual sliding path remains
separate, as do the explicit failed-native-Jump fallback and sustained-airborne
wall grab. Normal forward motion down a step can therefore start harmless probe
prewarming but cannot transfer coordinate or animation ownership to climbing.

## Static verification

`python tools/reverse-engineering/verify_climbing_issue_119.py` rejects the old
unconditional downhill predicate, requires player intent and stalled/backward
progress for inferred slips, and asserts that native slide, Jump, and genuine
fall entry paths remain present.

## Runtime acceptance

After integration build/install, walk and run both directions over the same
tiny rock and other ordinary steps. Arthur must keep vanilla step motion and
must never snap back, enter a ladder/climbing pose, or lose movement control.
Then separately verify that pushing uphill while actually losing ground, a
prequalified native steep-slope slide, Jump into a climbable wall, and steering
into a wall during a real fall can still attach. Static verification cannot
establish those player-visible outcomes.
