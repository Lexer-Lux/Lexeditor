# GitHub #50 - wanted duration and search areas

## Evidence

- The current update-layer `dispatch.meta` ships
  `SingleplayerWantedLevelRadius` values of 60, 75, 90, 115, 150 and 200 for
  clean through wanted level 5.  `MyOverhaul/dispatch.meta` has the same table,
  is already mapped to `update:/common/data/dispatch.meta`, and LEXEDITOR
  already round-tripped those values.  This is a real control for the active
  wanted/search circle radius.
- `dispatch.meta/HiddenEvasionTimes` is zero for every Story Mode wanted level
  in both the base and update-layer files.  It is not a defensible duration
  control for this game merely because GTA V used the similarly named table.
- The base and update-layer `tune/incidentstuning.meta` instead both ship
  `CBountyIncident/Evasion/TimeEvadingForEscape = 75.000000`.  The field name,
  its placement in the bounty incident's Evasion block, and the zero dispatch
  table are direct data evidence that this is the active pursuit/search escape
  timer.  `MyOverhaul/tune/incidentstuning.meta` is already mapped to
  `update:/common/data/tune/incidentstuning.meta`.
- `dispatch.meta/ParoleDuration = 9000` is the only named post-incident parole
  duration in the shipped dispatch schema.  It is therefore the real candidate
  control for the short post-search reacquisition phase described in the issue.
  The schema does not declare its unit and Story Mode scripts do not call it;
  engine code owns the transition.  The editor identifies the uncertainty
  instead of claiming that a static inspection proved the dark-red HUD state.
- `_downloads/natives.json` identifies the available law incident/wanted score
  queries and the separately named bounty-hunter global cooldown natives.
  Decompiled Story Mode scripts use the latter with
  `BOUNTYHUNTERSGLOBALCOOLDOWN`.  That cooldown controls later bounty-hunter
  responses, not the immediate post-search lawman state, so it was not exposed
  as a substitute.

## Implemented

- Kept the existing per-wanted-level circle-radius editor.
- Added `Time hidden before escaping (seconds)` to the same Dispatch & Wanted
  view.  The API reads and writes the real nested `incidentstuning.meta` field
  while retaining its owning file.
- Renamed the previously exposed raw `ParoleDuration` row to
  `Post-search parole / reacquisition duration` and added help that preserves
  the raw-unit/runtime-verification boundary.
- Made the active timer visually identify `incidentstuning.meta`, preventing
  users from editing the all-zero `HiddenEvasionTimes` table under the false
  impression that it is the Story Mode search duration.

## Validation

- `python -m py_compile editor/server.py` passed.
- The inline JavaScript in `editor/editor.html` compiled with Node's `vm.Script`.
- A temporary isolated `LEXEDITOR_MOD_ROOT` round-tripped all three controls:
  wanted-level-5 radius 200 -> 650, escape time 75 -> 180, and parole duration
  9000 -> 45000.  The real mod data was not edited.
- `python tools/reverse-engineering/verify_wanted_system_issue_50.py` passed
  after the trace expansion. It checks every observed native, the documented
  F8 marker, nearby-ped/minimap correlation, and absence of the known law-state
  mutators.

## Remaining acceptance boundary

Static evidence proves the active-circle radius and active escape timer.  An
in-game A/B test must establish how `ParoleDuration` maps to the exact dark-red
lawman presentation and confirm its unit.  These vanilla global tunables also
do not prove that the engine can retain and draw several simultaneous historic
crime exclusion circles.  If that multi-location map outcome is required, it
needs a separate persistent runtime/map-overlay system rather than a fake
LEXEDITOR control.

## Automatic runtime trace prepared

- Added `GameplayTweaks/modules/wanted_system.cpp`. It samples the exposed law
  incident, wanted score/level, HUD crime, dispatch response, witness,
  investigator, any-law-investigating, time-since-last-seen and registered
  crime states, with player coordinates and an elapsed clock.
- The trace starts automatically when any relevant law state appears and shows
  an in-game feed confirmation. No undocumented hotkey is required. It keeps a
  configurable 180-second tail after the exposed active states clear, which is
  the interval needed to correlate the visible dark-red-lawman phase with the
  engine states and `ParoleDuration`.
- The probe is intentionally observational. It never reports a synthetic
  crime, changes wanted score, or resets/extends an incident; doing so before
  identifying the actual post-search state would contaminate the A/B result.
- Expanded each sample with the configured wanted-level radius, distance from
  the trace origin, and a capped inventory of nearby hostile/in-combat/blipped
  human peds (model, relationship group, relationship, combat, entity-blip,
  minimap, on-screen and distance state). This distinguishes lingering lawmen
  from the engine-owned police-radar layer, whose dots are not always durable
  entity blips.
- Added a documented F8 visual marker. Pressing it when the dark-red dots begin
  and again when they end writes exact `VISUAL_MARK` timestamps and confirms
  each edge in the feed. The automatic trace still runs without key input; the
  marker supplies the missing player-visible ground truth in the same log.
- Added `GameplayTweaks/ini-fragments/github-50.ini` and
  `tools/reverse-engineering/verify_wanted_system_issue_50.py`.

### Integration handoff

The integration owner must include `modules/wanted_system.cpp`, call
`loadWantedSystemSettings()` during settings load,
`initializeWantedSystemTrace()` once after paths/settings are initialized, and
`updateWantedSystemTrace(player, ped, now, blocked)` once per frame. Merge the
issue INI fragment into the shipped INI. The feature agent did not build,
install, or edit the integration-owned dispatcher.

### Runtime A/B still required

After integration/install, commit a normal reported crime, escape the active
search circle, remain near the dark-red lawmen until they return to normal,
press F8 when the dark-red dots appear and again when they disappear, then
provide `GameplayTweaks.wanted-trace.log`. Repeat once with a deliberately
different `ParoleDuration`. The paired visible timings and state transitions
are required before implementing re-entry pressure or persistent multi-area
circles; neither behavior is claimed complete from this trace alone.
