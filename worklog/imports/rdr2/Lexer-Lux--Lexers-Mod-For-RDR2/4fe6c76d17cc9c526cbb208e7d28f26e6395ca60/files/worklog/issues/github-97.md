# GitHub #97 - free climbing safety pass

## Evidence

The live game-root `GameplayTweaks.climbing.log` recorded the reported fatal
top-out directly. Immediately after `topping_out -> grounded
reason=verified_top_out_complete`, the ped had `velocityZ=9.99336`. The top-out
code released the ped to physics and only then cleared the looping ladder task,
so the animation mover could become an impulse after ownership changed. The
existing `g_climbTopOutAt` cooldown could not help because it was declared and
read but never assigned.

The lateral path never reached Arthur's authored narrow-ledge motion. It guessed
the clips `walk`, `walk_loop`, `move_walk`, `shuffle`, and `idle`; the shipped
string table instead identifies the exact entries
`mech_loco_m@character@arthur@terrain@unarmed@narrow_ledge@idle_left` and
`...@walk_left`. It also issued a task and queried `IS_ENTITY_PLAYING_ANIM` in
the same frame even though animation task binding is asynchronous. Failure
silently fell back to moving a static ladder hand-up pose sideways, matching the
reported broken traversal.

The slide transition was late by construction: expensive surface probes began
only after Rockstar's native slide task was already active. Once a later batch
resolved, the mod stole the ped and blended to the climbing anchor, producing
the visible slide-then-glitch state change.

Finally, the fitted surface normal fluctuated across irregular rock and the
code repeatedly pitched the entire ped to each new normal. Re-pitching a live
full-body task repeatedly shocks world-space cloth simulation, which explains
the coat-tail instability.

## Implementation

- Surface probes now pre-warm while the player presses into a face. An
  automatic slide grab is accepted only if that face was already cached before
  the native slide began. A slide that was not prequalified remains wholly
  native instead of changing mode late; Jump remains the explicit grab path.
- Lateral motion uses the shipped `walk_left` narrow-ledge clip directly and
  no longer performs guessed-name or same-frame playback probes.
- The surface pitch is captured at attachment and held stable for the climb;
  yaw still follows a consistently detected new face. This avoids repeatedly
  shocking cloth while retaining the fitted lean.
- Top-out clears the ladder mover before releasing physics, makes the grounded
  release the final position/rotation/velocity writer, assigns the cooldown,
  and suppresses any impossible solver/mover impulse during the first 500 ms.

## Static verification

`python tools/reverse-engineering/verify_prone_climb_parity.py` passed all 33
reference-derived invariants. The issue-specific
`python tools/reverse-engineering/verify_climbing_issue_97.py` passed all nine
guards. `git diff --check --
GameplayTweaks/modules/movement.cpp` reported no whitespace errors (only the
checkout's expected LF-to-CRLF warning).

## Integration and runtime boundary

The implementation changes the existing climbing owner in
`GameplayTweaks/modules/movement.cpp`; no dispatcher or INI registration is
needed. The integration agent must run the combined build, install and
hash-verify the resulting ASI after RDR2 closes, then test these four cases in
game:

1. Walk/push onto a steep face: either the mod grabs before a visible native
   slide, or the entire slide stays native; it must never switch late.
2. Traverse both lateral directions and confirm the authored narrow-ledge motion
   plays rather than a static grip sliding across the wall.
3. Climb irregular angled rock while wearing a long coat and confirm the tails
   remain stable as the fitted normal changes.
4. Top out on a ledge and confirm Arthur settles at zero launch velocity, does
   not clip sideways through the lip, and cannot immediately re-grab it.

No compile, install, GitHub state change, commit, or push was performed here.

## 2026-08-10 correction

The next in-game report disproved four parts of the preceding pass: W+Space
could attach to the building behind Arthur, lateral movement was absent,
releasing movement left the climb animation running, the custom top-out still
clipped, and walking off a ledge still fell normally.

The source causes were repaired in `modules/movement.cpp`:

- Reverse ledge probes are now forbidden during a manual Jump candidate and
  angle down toward the face below the departing ped. The walk-off window is
  650 ms and accepts a verified reverse contact after 70 ms/0.12 m of fall,
  instead of waiting for the ordinary 160 ms/0.35 m midair-grab threshold.
- The inferred-slope path attaches at the first already-verified loss of
  footing instead of waiting 140 ms and visibly switching out of a slide.
- Authored motion binding uses animation phase plus a bounded asynchronous task
  allowance rather than the unreliable `IS_ENTITY_PLAYING_ANIM` predicate.
  Releasing either lateral or vertical input explicitly stops the outgoing
  clip before the idle grip is issued.
- A verified walkable lip no longer uses the ladder `get_on_top_front` clip or
  a custom coordinate Bezier. Kinematic ownership is released and Rockstar's
  Story Mode `TASK_CLIMB` native owns the mantle. The module only observes the
  native climb/vault state; if collision refuses or stalls it, Arthur is safely
  settled on the already-verified landing rather than launched by the removed
  mover.

`python tools/reverse-engineering/verify_climbing_issue_97.py` passed all 20
current guards. The combined build/install hash and runtime acceptance remain
pending.

The combined release build succeeded and all 33 prone/climbing parity
invariants passed. Queued ASI SHA-256:
`1EF0C29A5DD946673827ECDDEA1B5C6800BD148B5F2E3111256A5446CBA2707A`.
RDR2 was running, so installation remained pending.

Rebuilt with the #5/#128 integration as ASI SHA-256
`AEAE1D1D1C53861A6F507815030957D333E77D097E9F2E7F899EF5B2FF82B2A3`;
installation remained pending while RDR2 was running.
## fuckups.txt recurrence audit

- The latest runtime test proves the existing static guards did not restore lateral traversal, stop the animation on release, or acquire a ledge when walking off. A passing verifier over intended branches is not execution proof.
- The repaired path must log the selected surface/direction, active animation, release cancellation, and reverse-mantle-to-climb transition, with bounded survival/readback checks. The accepted vanilla top-out is preserved; the three failed behaviors remain actionable.
