# GitHub #67 — Hunter's Hatchet Rework

## Evidence

- The previous runtime detected `WEAPON_MELEE_HATCHET_HUNTER` damage, forced
  every target to quality tier 2, set health to zero, and cleared the last
  weapon-damage record. That upgraded poor/good animals instead of preserving
  their original tier and risked erasing evidence Rockstar's carcass pipeline
  still needed.
- Story scripts use `PED::_GET_PED_QUALITY` / `PED::_SET_PED_QUALITY` for the
  animal quality tier. Legendary hunting-zone scripts create ordinary base
  models with named meta outfits (plus unique boar/Tatanka models), and own the
  spawned animal as scripted state.
- Story scripts use `ENTITY::HAS_ENTITY_BEEN_DAMAGED_BY_ENTITY(..., Global_35,
  1, 1)` to attribute damage to the player.

## Implementation

- Moved the feature into `modules/hunter_hatchet.cpp` and removed its old
  implementation from `world_economy.cpp`.
- Cached each continuously nearby ordinary animal's quality before a hit.
- Required both the exact non-rusted Hunter's Hatchet damage record and player
  damage attribution, restored the cached tier, and killed a surviving target
  once with the player passed as the health-change source.
- Excluded human peds, all mission-owned animals, every animal while the main
  mission guard is active, and the known Story legendary model/meta-outfit
  identities.
- Did not add inventory, spawn carcass/loot, or clear Rockstar's damage record;
  Rockstar remains the sole harvesting and loot owner.

## Verification and handoff

- `python tools/reverse-engineering/verify_hunter_hatchet_issue_67.py` passed
  all static contracts.
- Integration must include `modules/hunter_hatchet.cpp` after
  `modules/world_economy.cpp`, then perform the shared build/install.
- In-game acceptance remains: strike poor, good, and perfect ordinary animals
  with the Hunter's Hatchet; each must die from that hit and retain its starting
  carcass/pelt tier. Confirm a legendary hunt and a mission/script animal retain
  vanilla behavior, and skin/pick up one carcass to confirm no duplicate yield.
- Static evidence cannot prove the engine's visible death timing or final
  carcass yield; those remain in-game checks.
