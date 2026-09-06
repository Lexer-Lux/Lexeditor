# GitHub #113 - false climbing takeover at a railing

## Runtime evidence

The live `GameplayTweaks.climbing.log` captured the reported event at tick
585190328. Sixteen milliseconds earlier Arthur was grounded and running forward
at 2.95 m/s beside a cached vertical contact (`normal.z=0`). The next frame
entered `grounded -> grabbing reason=midair_contact` without Jump, a native
slide, or a failed native traversal. The mod then snapped him to the contact at
`-1797.61,-380.47,159.05`, entered the ladder grip, and retained climbing
ownership until tick 585226968. That directly accounts for climbing the railing
and the prolonged in-place orientation behavior.

The trigger was the automatic midair-grab predicate accepting a transient
`IS_ENTITY_IN_AIR`/falling report on its first frame whenever forward was held.
Uneven collision and railings can produce that report while the player is still
effectively on the ground. The mod had no duration or ground-clearance check.
The initial collision dip happened before the mod took coordinate ownership;
the erroneous railing attachment and prolonged rotation were caused by this
climbing path.

## Defensive fix

Automatic midair attachment now requires at least 160 ms of continuous airborne
state and at least 0.35 m of actual ground clearance. A one-frame or
collision-sized ground flicker therefore cannot enter climbing. The explicit
Jump fallback, prequalified slide takeover, and genuine cliff-fall grab remain
independent. Airborne duration is accumulated only in the Grounded climbing
state, so time spent in an owned climb cannot accidentally pre-arm a re-grab
after release. The climbing trace now records airborne age and ground clearance
so any recurrence is attributable without inference.

## Static verification

`python tools/reverse-engineering/verify_climbing_issue_113.py` checks the new
continuous-airborne and clearance gates, confirms the automatic midair path uses
them, and confirms manual Jump and slide entry remain independent.

## Runtime acceptance

After the integration build is installed:

1. Sprint and run along/into the same railing and other uneven low obstacles.
   Arthur may react with vanilla collision movement, but must never snap into a
   ladder pose, rotate in place, or enter a mod-owned climb without a real fall.
2. Walk off a climbable ledge, keep steering into its face, and confirm the mod
   can still grab after Arthur has visibly cleared the ground.
3. Press Jump into a climbable wall and confirm the failed-native-jump fallback
   still attaches normally.
4. Trigger a prequalified steep-slope slide and confirm its automatic climbing
   takeover still works.

No build, install, GitHub mutation, commit, push, or game control was performed.
