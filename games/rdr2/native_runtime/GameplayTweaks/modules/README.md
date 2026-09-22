# GameplayTweaks source modules

GameplayTweaks still ships one `GameplayTweaks.asi`. `script.cpp` owns the
native wrappers, shared runtime/configuration state, and `ScriptMain`, then
includes these files in dependency order into one translation unit.

Keeping a single translation unit is deliberate for this first structural
split: the original implementation relies heavily on file-local `static`
state and functions. Including topic modules preserves that linkage, object
lifetime, and frame order exactly while allowing unrelated features to be
edited in different files. Do not add `modules\*.cpp` separately to the `cl`
command unless their shared state has first been moved behind explicit headers.

- `collectibles_map.cpp`: collectible/map markers and train blips.
- `world_economy.cpp`: reloads, shops, unique items, money, camera, bounty,
  bloodstain, and campsites.
- `items_casings.cpp`: spent casings, bottle recovery, and carried masks.
- `combat_inventory.cpp`: combat/input bridges, carry pools, radial ammo,
  binocular access, and projectile visibility.
- `recon.cpp`: binocular recon tagging and plant/object markers.
- `movement.cpp`: stamina controllers, prone, climbing, and core-XP policy.
  The #261 surface/state repair is guarded by
  `tools/reverse-engineering/verify_climbing_surface_state_issue_261.py`.
- `horse_persistence.cpp`: owned-horse position persistence across restarts.
