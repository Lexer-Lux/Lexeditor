# Legacy camera buttons under Modern Controls

Live issue #329 is untested. Latest user request supersedes preserving native
shoulder control: camera-left/right and overhead camera button must do nothing.

## Current candidate (2026-09-19, second replacement)

Human acceptance: the old camera buttons are correctly disabled with Modern Controls on. Clock, Squall MAG and startup also passed their separate checks. Keep those accepted fixes.

New failed test: in battle, the camera could move underground but barely move upward. The elevation calculation treated positive Y as up; FF8 battle coordinates use positive Y down. The replacement reverses that conversion at both read and write, so the floor and upper angle operate in the correct direction. Scripted-camera ownership and the world-map controls are unchanged.

The driver was rebuilt, package-checked and installed. Compiled orbit tests cover both vertical extremes, scene floors, dead zone, speed, radius and native handoff; the 1,024 legacy-button cases still pass. In-game acceptance is pending.

Acceptance test (no build needed):
- [ ] Restart FF8 with Modern Controls enabled and enter a battle. Use the right stick to move above the party, then down toward ground level. The camera must have a useful upward range and stop before moving underground.
- [ ] Release the stick: no drift. Trigger an attack: the scripted camera must still work and hand control back afterward.
- [ ] Report the battle/location and a screenshot if either limit is wrong.

Installed candidate: `D:/SteamLibrary/steamapps/common/FINAL FANTASY VIII/AF3DN.P`, SHA-256 `398062ac3da8c632bcb75410dd51406792c11bafa85108fe5f4913f553c68663`. The prior driver was backed up. Settings and saves were preserved. No visible game window was opened.
