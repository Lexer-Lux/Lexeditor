# Worklog: Todo 150

## #150 — no way to move the pause map view, 2026-08-04

Searched the complete native surface (`_downloads/grep_natives.py`) for MAP,
CURSOR, WAYPOINT, MAP_ZOOM, PAUSE_MENU, MINIMAP_COMPONENT, MAP_CENTRE/CENTER,
SET_MAP, ACTIVATE_FRONTEND, FRONTEND_MENU, OPEN_MAP. The MAP namespace covers
blips, fog of war (`SET_MINIMAP_FOW_REVEAL_COORDINATE`, `_REVEAL_MINIMAP_FOW`),
`LOCK_MINIMAP_ANGLE`, `_SET_MINIMAP_ZONE`, `_SET_RADAR_CONFIG_TYPE` and waypoint
getters. Nothing sets a view position.
`map_app_event_handler.c` line 100 creates its only databinding list from path
`"MapFocus"`, carrying `Region`, `ItemHovered`, `HoveredName` — hover state, not
a camera. No write target.
No native opens or closes the map, so the close/reopen workaround (the map opens
centred on the player) cannot be triggered either.
UNBLOCK PATH: find the global holding the map view position, same technique as
`Global_1914319.f_16855.f_31` for the Post Office rows (#93).

