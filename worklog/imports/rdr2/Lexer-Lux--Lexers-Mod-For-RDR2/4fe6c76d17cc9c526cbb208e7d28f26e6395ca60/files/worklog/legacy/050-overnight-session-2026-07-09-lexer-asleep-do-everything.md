# Worklog: 050 Overnight Session 2026 07 09 Lexer Asleep Do Everything

## Overnight session 2026-07-09 (Lexer asleep, "do everything")

- **GUI/OpenIV work is impossible while the PC is LOCKED.** Symptom: window
  reports visible (Windows API) but computer-use screenshot only shows a static
  wallpaper; mouse_move shows no cursor. File ops + compiles still work. So the
  OpenIV-dependent items (vignette .ytd, skip-movies startup.ymt, #8 blip
  config, #9 bonding tuning) are blocked until the screen is unlocked. Do NOT
  drive OpenIV blind — edit-mode mistakes corrupt game files.
- Window can be on a monitor the capture misses; move it with user32 MoveWindow
  via PowerShell (Add-Type). But if the desktop is locked, capture still fails.
- DONE this session (file-based): GameplayTweaks.asi rebuilt with #4 minimap +
  #7 animal density (off by default) + #11 human/horse stamina drain+recovery
  (natives: SET_PLAYER_STAMINA_RECHARGE 0xFECA17CF3343694B, _SET_PLAYER_STAMINA_
  SPRINT_DEPLETION 0xBBADFB5E5E5766FB, PED _SET_STAMINA_DEPLETION 0xEF5A3D2285D8924B
  / _SET_STAMINA_RECHARGE 0x345C9F993A8AB4A4, GET_MOUNT 0xE7E11B8DCBED1058);
  installed to game root. Editor reference dataset repointed kiddos->prices1899.
  Lexer supplied 1899 Economy Overhaul v7.1 on 2026-07-12; its catalog and
  reward table now load locally as a read-only reference (5,049 items / 349
  effects verified). Third-party files are gitignored and must never ship.
- On 2026-07-13 Lexer explicitly requested 1899's buy/sell values as the
  MyOverhaul starting point. All 5,049 reference records map to MyOverhaul
  (4,658 direct IDs, 391 proven JOAAT matches); its cash prices were mirrored
  while MyOverhaul purchase quantities, unlocks, recipes, effects, and shop
  membership were retained. Ten newer records with no 1899 counterpart remain
  unchanged. This also restored sell prices to all 144 cigarette cards. Treat
  the wholesale third-party value set as temporary reference debt: independently
  revise/rebuild it before public release under the from-scratch rule.
- #9 bonding: no rate native (_SET_MOUNT_BONDING_LEVEL only sets level); needs
  the bonding tuning data file. #8 markers: no SET_BLIP_ALPHA native.

