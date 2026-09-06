# GitHub #173 - Rolling Doesn't Always Remove Stamina

## 2026-08-10 recurrence audit before implementation

- The live reproduction was to mash SPACE for rapid rolls: the first roll
  spent Stamina and the next could spend none.
- Primary evidence was the hash-pinned `CombatRoll.asi` engine predicate, the
  active #6 state machine, and installed roll trace entries with exact accepted
  costs such as `81.6->71.6 requestedCost=10` and
  `42.2918->9.29181 requestedCost=33`.
- The trace ruled out an inconsistent Stamina native for accepted replacement
  P1 tasks. The actual defect was ordering: the update returned throughout P1
  and P2 before it sampled the engine predicate, so it could miss the false
  interval and fail to recognize a rapid second true edge. That second engine
  roll then bypassed both replacement P1 and its charge.
- The recurring false-success risk was to log the requested cost without
  proving the bar changed. Each accepted P1 needed one immediate readback and
  an explicit expected-versus-actual comparison, with expected spend clamped
  to the available bar amount.
- The sanctioned repair was to sample and queue predicate edges before the
  active-stage return, keep the pending pair until the current P2 released
  ownership, and charge once when the queued P1 was issued. No repeated
  per-frame Stamina write, input suppression, invented cooldown, or coordinate
  mutation was permitted.
- Static proof had to establish the ordering, one charge site, and readback.
  Player-visible acceptance remained at least two rapid rolls with nonzero
  starting Stamina, where each accepted roll reduced the bar by the configured
  cost or by the remaining amount down to zero.

## 2026-08-10 implementation

The predicate sample and rising-edge queue now execute before the active P1/P2
advance and return. A second engine edge can therefore be retained while the
first replacement roll owns the ped and can start after P2 finishes. The pair
snapshot prevents later input changes from altering that accepted edge.

Each accepted P1 now increments a sequence and performs exactly one Stamina
write followed by immediate readback. The trace compares actual spend with the
configured cost clamped to the bar value that existed before the write. A bar
that reaches zero is therefore a valid clamped postcondition, not an apparent
missing charge.

`verify_dodge_roll_issue_173.py` passed the predicate-before-return ordering,
single-charge-site, P1-to-charge ordering, and readback guards. The #6/#172
verifiers and all adjacent climbing, prone, and #144 verifiers also passed. No
build or install was performed. Runtime remains decisive: rapid consecutive
rolls must produce separate sequence records and matched bar reductions.
