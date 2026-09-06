# GitHub #177 - Weirdness With A Weapon Drawn

## Recurrence audit before source edits

- **Primary evidence:** the live issue reports a visible camera move when a
  weapon is drawn even though the editor remains on `Standing`. The local
  native database resolves `0xBDD9C235D8D1052E` as
  `_IS_PED_CURRENT_WEAPON_HOLSTERED`; Story scripts use its negation as the
  weapon-out condition (`mary3.c:73757/73776`, `mudtown4.c:65346`,
  `train_robbery2.c:35367`, `sadie2.c:56138`).
- **Sanctioned path:** classify Rockstar's armed follow-camera state and give it
  a separate profile. Do not draw/holster a weapon or infer the state from a
  transient animation name.
- **Execution proof:** bounded samples must name raw/applied mode, holster
  state, configured values, and rendered lateral/orbit/vertical coordinates.
  A submitted setter is not proof of visible placement.
- **Player-visible acceptance:** drawing a weapon must select `ARMED`; holstering
  must return to `STANDING`. Crouched equivalents must work independently.
  Each profile must be editable and must not flash through the other profile.
- **Cadence:** holster state and camera coordinates are reads. The documented
  camera parameter remains frame-scoped. No weapon/task state is written.

## Source result

Added `Armed` and `CrouchedArmed` modes after the existing profile IDs. They use
the resolved holster predicate and have distinct persisted key prefixes. The
telemetry now reports `drawn`, raw mode, and applied mode. Default values match
their holstered counterparts, so the split does not invent a new composition;
it lets Lexer tune the real second rig.

Integration must add `ArmedShoulderOffset`, `ArmedDistance`, `ArmedLowCamera`,
`CrouchedArmedShoulderOffset`, `CrouchedArmedDistance`, and
`CrouchedArmedLowCamera` to the shipped INI/settings schema. Runtime acceptance
is still required.
