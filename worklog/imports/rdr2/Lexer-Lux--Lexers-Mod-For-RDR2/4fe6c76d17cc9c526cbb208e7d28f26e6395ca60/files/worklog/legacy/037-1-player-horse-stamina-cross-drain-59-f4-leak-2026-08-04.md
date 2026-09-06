# Worklog: 037 1 Player Horse Stamina Cross Drain 59 F4 Leak 2026 08 04

## #1 player/horse stamina cross-drain + #59 F4 leak — 2026-08-04

Build `0D77A42AEB5BB8AD6400FF13699CE42591B979E567F2124B94C5F5DFAE35A8B1`,
installed and hash-verified. Full restart required.

- #1 ROOT CAUSE, and it is a genuine regression that made the game worse than
  vanilla. `playerMovementStaminaRate(ped)` reads `IS_PED_SPRINTING`,
  `IS_PED_RUNNING`, `GET_DESIRED_MOVE_BLEND` and `ENTITY_SPEED` off the PLAYER
  ped. While mounted the player ped inherits the mount's speed and locomotion
  flags, so a galloping horse read as Arthur sprinting and `g_playerStaminaRate`
  drove `g_humanSprintRate` onto the player's own bar. Holding sprint on a spent
  horse therefore drained both meters from this one call - exactly the reported
  "when my horse's stamina core is drained it starts draining MY stamina".
  Fix: gate the player controller on `!IS_PED_ON_MOUNT && !IS_PED_IN_ANY_VEHICLE`
  (plus the existing climb gate) and reset it otherwise.
  NOTE: the horse-core-as-reserve half of #1 is NOT fixed by this and remains
  open. The reserve latch at `reserveTick` is unchanged.
- #59: F4 is read raw via `GetAsyncKeyState(VK_F4)`, so RDR2's own F4 binding
  still fired and opened the item/satchel wheel alongside the campsite hotkey.
  Fix: while F4 is physically down, disable `INPUT_OPEN_WHEEL_MENU`,
  `INPUT_OPEN_SATCHEL_MENU`, `INPUT_OPEN_JOURNAL`, `INPUT_SELECT_WEAPON` across
  all three control groups.

