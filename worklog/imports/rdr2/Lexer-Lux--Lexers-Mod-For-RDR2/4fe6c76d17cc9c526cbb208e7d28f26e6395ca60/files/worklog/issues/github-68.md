# GitHub #68 — Prone weapons and binoculars

## 2026-08-06 wheel-test unblock

The user's report that the weapon menu would not open was correct. Both the
source and installed INIs still had `GroundedAimMode=0`. In that mode
`BlockWeaponActions=1` deliberately disables `INPUT_OPEN_WHEEL_MENU`, so the
one-handed upper-body experiment described in the issue was impossible to
reach. The implementation comment said to set mode 1, but the test build was
shipped with it off.

The source INI now ships `GroundedAimMode=1`. Existing movement code derives
`g_proneOneHandedWeapons` from that value and, in mode 1, suppresses only Reload;
weapon wheel, aim, and attack remain readable. It permits only pistol, revolver,
and throwable one-handed classification for the face-down secondary upper-body
aim pose (`0x10000430`) while Rockstar retains native aim ownership. The unsafe
general fallback remains `BlockWeaponActions=1`, so disabling the experiment
still refuses unsupported actions instead of standing Arthur or leaving a
broken full-body pose.

`python tools/reverse-engineering/verify_prone_weapons_issue_68.py` verifies the
enabled source setting, hot-reload derivation, wheel path, one-handed weapon
classes, secondary animation flag, and that mode 1 blocks Reload but not wheel,
Aim, or Attack.

## Known limits and runtime acceptance

This change makes the existing decisive test reachable; it does not claim the
experiment succeeded. After the integration owner copies the INI (and builds
only if other queued source changes require it), enter prone, open the weapon
wheel, select a pistol and revolver, aim across a wide reticle arc, and fire at
near and distant fixed targets. Confirm the gun and impacts follow the reticle,
Arthur stays face-down, switching does not slide/freeze him, and Reload remains
refused. Also try a longarm and binoculars: no face-down authored animation is
known for either, so they must not be called complete from this pass.

If the one-handed gun does not track the reticle, the last no-new-animation
mechanism is disproven and one-handed combat joins longarms/reload/binoculars in
requiring an authored animation pipeline. No build, install, game control,
GitHub mutation, commit, or push was performed.

## 2026-08-06 safe wheel/equip ownership follow-up

The reachable test still cleared all primary ped tasks for the configured
700-millisecond draw window after wheel close. That relinquished the prone
skeleton and could stand Arthur before the grounded aim experiment even began.
The secondary one-handed aim loop also had no explicit Aim-up cleanup, so its
upper-body pose could remain layered over later idle/crawl playback.

The wheel-close bridge now latches only pistol, revolver, and throwable
selections and repeatedly asserts `SET_CURRENT_PED_WEAPON` during the existing
equip window while the root-motion-free prone idle remains authoritative. This
matches the useful part of the installed reference evidence (read current wheel
selection, then call `SET_CURRENT_PED_WEAPON`) without copying its canned timed
full-body animation or clearing the primary task. Unsupported longarms, bows,
and binocular wheel selections return to Unarmed because no accepted face-down
rig exists for them.

When Aim is released after the mode-1 one-handed experiment, the module now
clears only the secondary task it owns and resumes ordinary prone locomotion.
The rejected timer-driven back-roll and full-body one-handed paths remain hard
disabled. Reload remains blocked.

`verify_prone_weapon_bridge_issue_68.py` checks the one-handed classification,
latched repeated equip, absence of primary task clearing in the bridge,
unsupported-selection refusal, secondary Aim-up cleanup, and that both rejected
paths remain disabled.

No visual success is claimed. Runtime acceptance must still confirm that a
pistol/revolver visibly remains in hand after wheel close without standing or
sliding, wide reticle arcs and impacts track correctly, Aim-up returns cleanly
to prone idle/crawl, firing works, and Reload remains refused. Longarms, reload,
and face-down binocular use remain unresolved pending an authored RDR2 animation
pipeline; the existing safe binocular policy may exit prone before yielding to
the native binocular task, but that is not prone binocular use.

Lexer's test decisively rejected `GroundedAimMode=1`: selection did not commit,
aiming produced a jittering seated pose, the gun did not track, and firing was
impossible. The release default is restored to 0 so the failed experiment is
not shipped as functionality. This issue remains actionable; it is not a fix.
