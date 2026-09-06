# GitHub #45 - Casing ejection tuning

## Requirement

Make collectible casings originate at the weapon and leave it with visible,
weapon-relative momentum rather than materializing and falling straight down.
The requested method was to temporarily restore vanilla shell visuals as a
reference, tune against them, then remove the reference.

## Reference boundary

The settled whole-stack audit in `codex/runtime-engine-limits.md` proves the
shipped base weapons file and all six per-weapon patches have blank shell-effect
fields. There is no live vanilla shell-ejection VFX to restore, so enabling a
reference would be fabricated. The implementation instead exposes the actual
physical parameters and logs their observed world-space result for one focused
runtime tuning pass.

## Implementation

`items_casings.cpp` now reads `[CasingEjection]` on every spawn. Spawn position
uses the current weapon entity's right/forward/up matrix, with a hand-height ped
fallback only when the weapon entity is unavailable. Initial velocity inherits
the player's world velocity and adds configurable weapon-local right, forward,
and upward ejection plus bounded random variation. Reload dumps use configurable
ordinal spacing and lower momentum so several retained cases fan out naturally.
Each casing starts at a randomized orientation and keeps ordinary dynamic
physics, gravity, collision, pickup, glint, and lifetime behavior.

The casing log records exact world spawn, velocity, and whether the weapon or
ped matrix was used. The INI fragment contains all ten controls and defaults.

## Integration

Merge `ini-fragments/github-45.ini` into the shipped `[CasingEjection]` section.
No dispatcher change is required because `items_casings.cpp` is already loaded.
The integration owner performs the unified build/install/hash verification.

## Runtime acceptance

Fire pistols while stationary and moving; cycle repeaters, rifles and pump
shotguns; reload revolvers and break-action shotguns. Casings must visibly leave
the correct side/height of the weapon, inherit player motion, arc and tumble,
then collide and settle without spawning in Arthur. Reloaded cases should fan
out rather than share one point. Compare first and third person and left/right
dual-wield hands. Use `GameplayTweaks.casings.log` to tune signs/magnitudes if a
weapon family exposes a different local matrix. Static checks cannot establish
the final visual match.
