# GitHub #71 - Road travel stamina benefit

## Requirement

Player and current-horse outer-stamina drain uses half the configured movement-mode drain while actually on a road by default. Human and horse multipliers are independent and hot-reloaded. Recovery, swimming, cores, maxima, movement bands, and exhaustion behavior remain unchanged.

## Implementation

- Extended the existing movement-mode rate functions in `GameplayTweaks/modules/movement.cpp`; no second stamina controller was introduced.
- Used `PATHFIND::IS_POINT_ON_ROAD` (`0x125BF4ABFC536B09`) at the actor's exact coordinates. This avoids granting the benefit merely because a road node is nearby.
- Applied the multiplier only after movement-mode selection and only when the selected traveling rate is negative. This also behaves correctly if a user intentionally configures walking or trotting as drain rather than recovery.
- Returned swimming before road adjustment and left all non-negative standing/walking/trotting recovery paths untouched.
- Clamped each multiplier to `0.0..1.0` at use as a defensive boundary.

## Evidence

- `_downloads/natives.json` names `0x125BF4ABFC536B09` as `IS_POINT_ON_ROAD` and gives the signature `(float x, float y, float z, Vehicle vehicle) -> BOOL`.
- Story scripts use the same native for exact road occupancy, including `beat_stalking_shadows.c`, `camera_photomode.c`, `coachrobberies.c`, and `marston2.c`.
- Static inspection confirms swimming and every non-negative movement mode bypass the adjustment. The exact configured value is therefore preserved for ordinary standing/walking/trotting recovery.

## Integration required

The integration owner must add and hot-reload these shared settings in `script.cpp`:

- `g_humanRoadDrainMultiplier`, default `0.5f`, read from `[HumanStamina] RoadDrainMultiplier`
- `g_horseRoadDrainMultiplier`, default `0.5f`, read from `[HorseStamina] RoadDrainMultiplier`

Clamp both to `0.0..1.0`, document/add both `RoadDrainMultiplier=0.5` keys in `GameplayTweaks.ini`, then rebuild, install, hash-verify, and move the GitHub issue from `actionable` to `test me`.

## Runtime acceptance still required

Compare fixed-duration drain on-road and immediately off-road on foot and mounted, verify road-edge transitions do not flicker, verify swimming/recovery are unchanged, and verify `1.0` exactly restores the pre-issue rates.

## 2026-08-10 recurrence audit before road-speed extension

### Primary evidence / requested result

- The live issue body remains authoritative for exact-road drain behavior and
  its negative-rate-only boundary. The latest live comment adds two independent
  road speed multipliers: one for the human player and one for the current
  horse. It does not replace or broaden the drain feature.
- `_downloads/natives.json` and the named Story-script call sites remain the
  primary evidence for `IS_POINT_ON_ROAD` at exact actor coordinates. Story
  scripts also apply `SET_PED_MOVE_RATE_OVERRIDE` to both humans and mounts;
  `mary1.c` applies it directly to `PED::GET_MOUNT(Global_35)`.

### Sanctioned ownership path

Road occupancy is one sampled input, not a new locomotion controller. The human
road factor must be consumed inside `human_movement.cpp`, where #144/#156/#157
already own the one on-foot move-rate scalar. `movement.cpp` must not add a
second `SET_PED_MOVE_RATE_OVERRIDE` call for Arthur. The current horse is a
separate ped and may have its own frame-scoped move-rate scalar in the existing
horse stamina/movement update path. #6 dodge and #9 prone retain exclusive
ownership while active.

The composed human scalar is `base rate * gait multiplier * road multiplier`.
Road occupancy does not alter the walk/sprint ceiling, request a desired blend,
force a motion state, or otherwise fight the animation graph. Swimming and all
non-locomotion yield states bypass speed ownership.

### Actual execution / postcondition

The road sample must record both raw and stable state, the selected human/horse
multiplier, the applied rate, and entity speed. A call-site line is not enough:
the runtime heartbeat must distinguish no actor, off-road `1.0`, and on-road
configured scaling. Road transitions require bounded confirmation so a single
path-query flicker cannot alternate the scalar every frame.

### Player-visible acceptance

At a fixed input/gait, foot speed must change only while Arthur is physically
on the road and horse speed must change independently only while the current
mount is physically on the road. Stepping immediately beside the road must
remove the benefit promptly without oscillation. Setting either speed
multiplier to `1.0` must restore that actor's pre-extension speed. Drain tests
from the original issue still have to pass, including unchanged recovery and
swimming.

### Per-frame native inventory

- `IS_POINT_ON_ROAD` is a read, bounded to one 100 ms sample per tracked actor;
  two consecutive changed samples are required before the stable state flips.
- Human `SET_PED_MOVE_RATE_OVERRIDE` remains the sole #144 frame-scoped rate
  writer and consumes the cached road factor. No second human writer is added.
- Horse `SET_PED_MOVE_RATE_OVERRIDE` is frame-scoped and runs only while a valid
  current mount is on-road with a non-`1.0` factor. Off road, on dismount, while
  swimming, or at `1.0`, the issue writes nothing and the prior frame expires.
  `SET_PED_MAX_MOVE_BLEND_RATIO` remains human-only and never receives a
  road-derived value.

## Road-speed implementation and scoped result

- Replaced repeated exact-road reads with one cache per actor. Each cache calls
  `IS_POINT_ON_ROAD` at most once per 100 ms and requires two consecutive
  changed samples before changing its stable result. Player stamina and #144
  human speed consume the same player cache; horse stamina and horse speed
  consume the same mount cache.
- Added `[HumanMovement] RoadSpeedMultiplier` to #144's existing composed
  scalar. `human_movement.cpp` remains the only ordinary on-foot move-rate
  writer: `BaseMoveRate * Sneak/Sprint multiplier * RoadSpeedMultiplier`.
  Both new factors are bounded to `0.10..1.15`; `1.15` is the documented
  maximum for `SET_PED_MOVE_RATE_OVERRIDE` in `_downloads/natives.json`.
- Added `updateRoadHorseSpeed(horse, now)`. It reads
  `[HorseStamina] RoadSpeedMultiplier`, applies the frame-scoped move-rate
  scalar only to a valid non-swimming current horse while stably on-road and
  only when the factor differs from `1.0`, and otherwise lets the prior frame
  expire. This path is independent of the Horse Stamina Enabled switch.
- Added bounded transition, idle and five-second heartbeat logs with raw/stable
  road state, selected factor, writer state and actual entity speed.
- Added `GameplayTweaks/ini-fragments/github-71.ini` with neutral `1.0`
  defaults and `tools/reverse-engineering/verify_roads_issue_71.py`.

Scoped static checks passed:

- `verify_roads_issue_71.py`
- `verify_human_movement_issue_144.py`
- `verify_human_movement_issue_156.py`
- `verify_human_movement_issue_157.py`
- `verify_dodge_roll_issue_6.py`
- `verify_prone_climb_parity.py` (34 invariants)
- `py_compile` for the touched/related verifiers
- `git diff --check` for the #71/#144-owned files

## Exact integration required for the road-speed extension

1. Merge `GameplayTweaks/ini-fragments/github-71.ini` into the shared main INI
   and regenerate the settings-menu schema so both speed multiplier rows are
   user-editable. No new shared configuration globals are required; both
   issue-owned modules hot-read their own keys every two seconds.
2. In the existing per-frame player/mount update, call
   `updateRoadHorseSpeed(GET_MOUNT(ped), now)` regardless of
   `g_horseStamEnabled`. Calling with no mount is intentional and supplies the
   idle/yield diagnostic. Do not call it from `horseMovementStaminaRate`, the
   Show Mode renderer, or another conditional path.
3. Keep `movement.cpp` included before `human_movement.cpp`; the latter consumes
   `movementPlayerOnRoad` directly. Do not add any human move-rate write to the
   shared dispatcher.
4. SUPERSEDED 2026-08-10. This step used to say to keep shared
   `[HumanMovement] Enabled=0` for the ordinary installed build. That was a
   caution from a pass where the #144 rework was unproven, not a decision by
   Lexer, and it directly contradicts #144 being an open feature he wants in
   play. The shipped value is `Enabled=1` and stays that way. Build/install/hash
   verification still does not establish the clean-session animation
   postcondition; that remains a runtime check, not a reason to ship the
   feature off.

Runtime acceptance remains required for both independently configured speed
factors, exact road/off-road transitions, `1.0` parity, and all original drain
boundaries. Logs must show `raw`, `stable`, selected factor, writer state and
actual speed; setter execution alone is not acceptance.
