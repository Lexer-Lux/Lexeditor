# Worklog: 068 189 Camera Calibration 103 Optional Feed 2026 08 04

## #189 camera calibration + #103 optional feed — 2026-08-04

Build `F8205FDD80B2F0260D07E2D0B9645FF6A9CF0370CAB504766A6D82461802A6F4`.

#189. The native surface exposes exactly two third-person camera knobs:
`_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` (0x066167C63111D8CF) taking
(speed, respectHorizontalOffset, horizontalOffset, respectDistance, distance),
and `_FORCE_THIRD_PERSON_CLOSE_THIS_FRAME` (0x718C6ECF5E8CBDD4). Searched the
whole CAMERA namespace: there is NO vertical/height offset native, so the
requested X/Y/Z is X and Y only. The horizontal offset is SIGNED, which is the
proof the TODO asked for that left/right shoulder is one mirrored value rather
than two profiles.
`updateGameplayCamera` applies per-stance offset+distance every frame, keyed off
`customProneActive()` / `GET_PED_CROUCH_MOVEMENT`. Bails out for missions, aim
cam, cinematic cam, non-gameplay cam, vehicles and mounts.
Calibration mode draws the live values and edits the CURRENT stance's pair:
numpad 4/6 offset, 8/2 distance, shift = 0.005 steps instead of 0.02, numpad 5
writes all six values back to the ini via WritePrivateProfileStringA.
`LockToOneThirdPersonZoom` calls the force-close native each frame, which is what
removes the two intermediate zoom steps.

#103. Wired `announceItemGranted("Empty Bottle")` to both PROVISION_EMPTY_BOTTLE
grant sites, behind `[EmptyBottles] ForceAcquisitionFeed`, default OFF.
Deliberately NOT a guessed HUD-notification native — the SDK has no
ADD_TEXT_COMPONENT_SUBSTRING_PLAYER_NAME and inventing a call chain would risk a
fake feed firing alongside a real one. It uses the mod's own on-screen text for
2.6 s, which is honestly ours rather than pretending to be Rockstar's.
Leave it off until the icon retest proves whether the native feed returned.
Restored Rockstar's own `GENERIC_BOTTLE` texture from `INVENTORY_ITEMS` in
`catalog_sp.ymt`; the custom `LEX_ICON_EMPTY_BOTTLE` replacement was unnecessary
and was the cause of the blank satchel icon when its custom dictionary failed.

