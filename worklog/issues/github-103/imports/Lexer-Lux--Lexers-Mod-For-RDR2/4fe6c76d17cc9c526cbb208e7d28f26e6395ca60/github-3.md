# GitHub #3 - Wagon-team stamina and vanilla-style HUD

## Requirement

While the player drives or rides in a horse-drawn vehicle, the harness team
must consume real horse Stamina and expose that state in the lower-left horse
Stamina position with a vanilla-looking core/bar. The separately installed
Hardcore Stamina mod was the visual reference, but its default core position
was explicitly not the desired final position.

## Evidence

- Every wagon supplies its own harness horses. The player's owned mount cannot
  be substituted into the team.
- `_SHOW_HORSE_CORES` accepts only a boolean and therefore remains hardwired to
  the player's owned mount. The decompiled Story Mode scripts contain no
  ped-targeted alternative for pointing the stock horse HUD at a draft horse.
- The local reference is
  `_downloads/inspect/hardcore-stamina/Y_Hardcore_Stamina.asi`. Static string
  and xref inspection proved it uses Rockstar's resident `rpg_textures` stack:
  `rpg_meter_track_9`, `rpg_meter_track`, `blip_player_coach`, and
  `rpg_meter_0` through `rpg_meter_99`. Its draw order/colors are black backing,
  gray 109 track, white coach core, and gray 229 live fill.
- The reference INI's normal dimensions, `WIDTH=242` and `HEIGHT=430`, are
  ten-thousandths of a 16:9 screen and resolve to a square about 46.5 pixels at
  1080p. Its default center `(140, 927)` was not copied.
- `fortification_hud.cpp` already records the measured vanilla horse-Stamina
  center for Lexer's HUD scale 1.0 / extended circular minimap setup as
  `(344.06, 723.75)` on a centered 1920x1080 reference canvas.
- `_CHANGE_PED_STAMINA` (`0xC3D4B754C0E86B9E`) explicitly accepts negative
  values. Direct core writes are not outer-stamina expenditure and were the
  wrong mechanic in the legacy wagon loop.

## Implementation

- Added the unregistered topic module
  `GameplayTweaks/modules/wagon_stamina.cpp`.
- Enumerates all valid harness horses with `_GET_PED_IN_DRAFT_SEAT` and renders
  the worst remaining outer-Stamina fraction, so one exhausted horse cannot be
  hidden by a fresher teammate.
- Draws only Rockstar's resident meter/coach sprites, at the measured vanilla
  horse-Stamina seat. It suppresses the custom draw with hidden HUD/radar,
  pause menu, cinematics, and other gameplay locks.
- Reinterprets existing `[WagonCores] DrainPerSecond` as real outer-Stamina
  points per real second. A monotonic per-horse target cancels native idle
  regeneration instead of letting it erase the requested drain.
- Never drains a Stamina Core. At the outer bar's visual floor it also restores
  an engine reserve-spend tick on these non-owned harness horses, matching the
  project's NoReserveCores policy.
- Added `tools/reverse-engineering/verify_wagon_stamina_issue_3.py` to assert
  the reference texture evidence and replacement module's static contract.

## Integration handoff

1. Include `modules/wagon_stamina.cpp` with the other topic modules.
2. Delete the legacy one-second `#19` WagonCores block that directly subtracts
   from `GET_CORE(horse, 1)` and its `lastWagonTick`/`wagonDrainBank` state.
3. Call
   `updateWagonStamina(ped, locked, g_wagonCoreEnabled, g_wagonCoreDrain,
   g_wagonMinSpeed, now);` once per frame.
4. Set `[WagonCores] Enabled=1` and revise its comments: Hardcore Stamina is no
   longer needed for the feature, and `DrainPerSecond` now targets the outer
   bar rather than the core.
5. Run the full integration build, install/hash verification, and knowledge
   index rebuild. No feature agent build or install was performed.

## Runtime acceptance boundary

After integration and installation, enter both a one-horse cart and a
multi-horse wagon. Confirm the coach core/bar appears exactly in the normal
horse-Stamina seat, its ring shows the lowest team member, movement above
`MinimumSpeed` drains the visible outer ring at `DrainPerSecond`, stopping does
not drain it, the horses' Stamina Cores never fall as backup reserves, leaving
the wagon removes the custom meter, and hidden radar/HUD, pause, and cinematics
never leave a floating icon. Exact draw registration and native stamina behavior
remain unverified until that in-game test.

The first live test rendered a white square. Adding `rpg_background` from the
reference binary's string inventory did not fix it; the second live test was
the same white square. That disproved both direct `rpg_textures` sprite stacks.
Issue #23 had independently established why: Rockstar's resident `rpg_meter_N`
art is a HUD mask rather than a transparent sprite, so direct `DRAW_SPRITE`
tints its opaque interior. The wagon module now uses the already-installed
DXT5 `generic_textures/lex_fortification_meter_1..99` alpha-backed rings for
the subdued full track and live fill. It also requests `BLIP_PLAYER_COACH` from
the actual `blips` dictionary instead of incorrectly requesting it from
`rpg_textures`. This candidate received static verification only; the parent
integration pass must build/install it, and the absence of the white square
still requires a fresh full-restart in-game test.
