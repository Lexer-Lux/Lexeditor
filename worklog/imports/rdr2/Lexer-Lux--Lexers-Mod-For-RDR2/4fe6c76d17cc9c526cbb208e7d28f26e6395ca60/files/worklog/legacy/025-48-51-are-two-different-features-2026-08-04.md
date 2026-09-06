# Worklog: 025 48 51 Are Two Different Features 2026 08 04

## #48 / #51 are two different features — 2026-08-04

They were wrongly merged. Lexer's specs:
- #48 Ancient Tomahawk: returns to inventory THE MOMENT it hits the ground or a
  target. Immediate, on impact.
- #51 every other loseable unique: turns up in the WEAPON LOCKER AT CAMP to be
  collected. Explicitly NOT handed back to the player.

`updateRecoverableUniques` implements NEITHER. It tracks first acquisition, waits
until `HAS_WEAPON`/`INVENTORY_ITEM_COUNT` are both zero AND `liveUniquePickup()`
finds no world pickup, then after a 30 000 ms delay calls `GIVE_WEAPON(playerPed,
unique.weapon)` — a delayed direct regrant. Wrong timing for #48, wrong
destination for #51. The acquisition tracking and pickup-liveness check are sound
groundwork; the delivery is what has to change, and #48 needs an impact hook
instead of a despawn poll.
`g_recoverableUniques` currently lists 7: WEAPON_THROWN_TOMAHAWK_ANCIENT,
WEAPON_MELEE_HATCHET_VIKING, _HEWING, _DOUBLE_BIT, _DOUBLE_BIT_RUSTED, _HUNTER,
_HUNTER_RUSTED. The Ancient Tomahawk must come OUT of this list once #48 exists.

