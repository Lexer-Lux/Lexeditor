# GitHub #145 — Horse Core Drain Hours Settings

## Requested behavior

The live issue requires independently editable horse Health- and Stamina-core
drain durations beside the existing Arthur/John CoreClock values. Both editor
surfaces must show the same saved/effective values and explain reload behavior.
The owned/current horse must actually use the horse durations without changing
the player rates.

## Primary-source and settled-mechanics basis

`_downloads/RDR2-Decompiled-Scripts/script_rel/player_horse.c:18293-18306`
maps horse core kinds 0 and 1 directly to core indices 0 (Health) and 1
(Stamina). Its `func_644` at lines 18339-18355 clamps 0..100 and calls
`ATTRIBUTE::_SET_ATTRIBUTE_CORE_VALUE`. This agrees with
`codex/runtime-engine-limits.md`: player and horse core fill must use only the
direct core setter; `SET_ATTRIBUTE_POINTS` is permanent progression and must
not be used.

The existing player CoreClock reads in-game minute deltas, drains 100 points
over each configured number of hours, accepts substantial scripted changes,
rejects ordinary one-point background metabolism, and clamps player drain-hour
settings to a 0.01-hour minimum. Horse CoreClock follows the same units,
calculation, 0.01 floor, 1200-minute sleep/fast-travel window, and reconciliation
rule without sharing any player-rate variable.

## Issue-owned implementation

`GameplayTweaks/modules/horse_core_clock.cpp` adds two independent settings:

- `[CoreClock] HorseHealthDrainHours`
- `[CoreClock] HorseStaminaDrainHours`

The module refreshes them from the INI every two real seconds. A change clears
only the affected horse controller's fractional banks, so the new rate applies
to future in-game minutes and never retroactively charges time accumulated under
the old value. No restart is required.

The runtime resolves Rockstar's owned saddle horse through `GET_OWNED_MOUNT`
and the currently ridden horse through `GET_MOUNT`. If they differ, both receive
their configured metabolism; a duplicate handle is processed once. Two bounded
states preserve separate fractional banks and are reset on handle/model
replacement. Entity/core reconciliation runs at four Hz rather than placing
four horse natives on every frame. Setter readback warns on mismatch, and a
30-second heartbeat distinguishes no target from a module that never executed.

`editor/settings_schema.json` labels all player rates explicitly as
Arthur/John and both new rates explicitly as Horse Health/Stamina Core Drain
Time. Player and horse drain settings now share the 0.01 minimum and help states
that changes reload within about two seconds with no restart. The existing
Core Clock wildcard puts the new INI keys beside the player equivalents.

`GameplayTweaks/modules/settings_menu.cpp` applies the same five-key numeric
validation before saving. This prevents the in-game menu from displaying an
invalid value while the runtime silently uses 0.01.

## Integration-owned registration

No shared file was edited. Integration must make these exact additions:

1. In `GameplayTweaks/script.cpp`, include
   `modules/horse_core_clock.cpp` with the other feature modules.
2. Call `updateHorseCoreClock(player, ped, now);` once per update after the
   existing horse reserve/controller block, so intentional configured drain is
   not mistaken for a reserve spend in the same frame.
3. In `[CoreClock]` of `GameplayTweaks/GameplayTweaks.ini`, place these beside
   the Arthur/John duration keys:

   ```ini
   ; Horse durations are independent of Arthur/John. They apply to the owned
   ; saddle horse and any different horse currently being ridden. Values are
   ; re-read within about two real seconds and affect future in-game minutes;
   ; no restart is required. Minimum effective value: 0.01 hours.
   HorseHealthDrainHours=24.0
   HorseStaminaDrainHours=24.0
   ```

No manifest, build/install, or GitHub label change belongs to this feature pass.

## Static verification and runtime boundary

`python tools/reverse-engineering/verify_horse_core_clock_issue_145.py` checks
the independent config fields, direct core setter and readback, owned/current
target resolution, duplicate/replacement handling, four-Hz cadence, clock-jump
window, heartbeat, primary-source native route, editor labels/help/ranges, and
in-game save validation. It passes before integration while reporting the two
integration-owned INI registrations as pending.

Static inspection does not prove in-game elapsed-time behavior. After the
combined build is installed, set visibly different player and horse durations,
save from each editor surface, read the INI back, observe the owned/current
horse across awake time and sleep, and confirm player drain remains unchanged.
## fuckups.txt recurrence audit

- A horse-rate setting is not implemented merely because it appears in both editors. The runtime must target the owned/current horse, use horse-core setters, and read back the result independently from Arthur/John's core clock.
- The module deduplicates owned/current horse handles and logs direct horse-core readbacks. Time-skip behavior while mounted and unmounted remains an explicit in-game comparison.
