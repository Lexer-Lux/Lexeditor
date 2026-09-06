# GitHub #179 - roll affordability gate

## Recurrence audit

- Read `fuckups.txt` before implementation. Refusing the custom animation after
  Rockstar has accepted the input is not prevention; the native roll would
  still happen for free.
- The primary engine path is Rockstar's own per-frame
  `DISABLE_CONTROL_ACTION(0, INPUT_DIVE, false)` at
  `beat_drunk_dueler.c:7950`, `mudtown3b.c:57928`,
  `braithwaites1.c:57448`, `sadie3.c:37055`, and `mary1.c:64301`.
- The reference Combat Roll trigger remains the hash-pinned
  `GET_PED_IS_DOING_COMBAT_ROLL` predicate. A Dive press alone never starts the
  replacement.
- A setter call is not acceptance. The production heartbeat records live bar,
  configured cost, affordability, gate state, suppressed-frame count, refusal
  count, and accepted-charge count. Any predicate edge that beats the gate is
  recorded as `engineRolledAnyway=1`.
- Player-visible acceptance is simple: when the outer Stamina bar is below the
  full configured roll cost, an on-foot roll must not start. Jumping, swimming,
  mounted movement, and vehicle controls must remain available.

## Repair

The roll updater now evaluates affordability before sampling the engine roll
predicate and before its active-stage return. If the on-foot roll feature is
enabled, cost is positive, and the live outer bar cannot pay the full cost, it
suppresses only `INPUT_DIVE` with Rockstar's exact per-frame form. It does not
suppress `INPUT_JUMP`, and it yields in vehicles, on mounts, and while
swimming.

Affordability is checked again immediately before P1 issuance because a queued
second roll can outlive the bar value that originally admitted it. Both refusal
points have distinct production records. Accepted P1 still uses the one #173
charge site through `StaminaRateController`, so prevention and payment cannot
disagree about which roll was accepted.

`verify_dodge_roll_issue_179.py` passed the five cited Story call sites, full-
cost comparison, per-frame gate ordering, context exclusions, issue-time
recheck, gate-breach trace, and absence of the removed cooldown substitute.
The #6 and #173 reference/charge verifiers also passed.

No build, install, shared-file edit, GitHub mutation, commit, or push was
performed. Runtime must confirm that a bar below cost produces no roll and a bar
equal to or above cost produces one charged roll.
