# Worklog: 062 98 Always Holster 50 Physical Bloodstain Marker 2026 08 04

## #98 always-holster + #50 physical bloodstain marker — 2026-08-04

Build `39D2A48E28491DED4AEE1D40928B9E95408665081FB31F96D2AF8424C8F873CD`.

#98. New `updateAlwaysHolster`. Latches `INPUT_HOLSTER_WEAPON` press, waits
450 ms for Rockstar's own holster to complete, then if `GET_CURRENT_WEAPON` is
still armed and `_IS_PED_CURRENT_WEAPON_HOLSTERED` (0xBDD9C235D8D1052E) is false,
calls `SET_CURRENT_PED_WEAPON(ped, WEAPON_UNARMED)`. Skipped in vehicles, on
mounts and during missions. `[AlwaysHolster] Enabled`.

#50. `BloodstainState` gains a `prop` Object. `ensureBloodstainProp` requests and
creates `p_moneybag01x` when the player is within 120 m, marks it a mission
entity, `PLACE_OBJECT_ON_GROUND_PROPERLY`, freezes it and disables its collision
so it cannot be kicked away or block movement. Recreated automatically if it
streams out. Removed on collection, on replacement by a new death, and on clear.
Money bag chosen over `p_gravestone05x` / `s_inv_moneyclip01x`: it is what was
actually dropped, and a grave marker misreads a death the player recovered from.

NOT DONE THIS BUILD, and not started: #182 (recon tags restyled as Rockstar core
rings), #189 (camera calibration mode), #131 (belt lantern), #42's camp greying,
#103's acquisition feed pending the icon retest, and every `!` computer-control
item (#8, #87, #175, #200).

