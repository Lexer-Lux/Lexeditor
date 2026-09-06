# Worklog: 064 131 Belt Lantern 42 Camp Greying 2026 08 04

## #131 belt lantern, #42 camp greying — 2026-08-04

Build `C25A566AE93E2E28A008B2E9C7457420D43BE137E0A9842BACDF40D6A3660944`.

#131. Removed both radial mappings from `MyOverhaul/quickselectitems.ymt`
(`WEAPON_MELEE_DAVY_LANTERN`, `WEAPON_MELEE_LANTERN_ELECTRIC`); backup at
`quickselectitems.ymt.pre-lantern`. New `updateBeltLantern` attaches
`p_lantern04x` to pelvis bone 11816 at offset (0.14, -0.06, -0.02), collision
off, and calls `DRAW_LIGHT_WITH_RANGE` at the prop position each frame.
Conditions: `GET_CLOCK_HOURS()` inside the configured night window, NOT crouched
and NOT in stealth movement, not in an interior, not in a mission, not swimming,
not dead. The prop is deleted whenever those stop holding, so crouching visibly
puts it out. `[BeltLantern] Enabled/LightsAtHour/OutAtHour/Range/Brightness`.

#42 camp greying. `radialAvailable` came only from availability bit 8 of the
`short_update` global, which does not cover camp. Now also forced false when
`SCRIPT_REFS(joaat("player_camp")) > 0`, or the ped is dead, in a vehicle,
mounted, ragdolled, swimming, using a scenario, or already in an item
interaction.

