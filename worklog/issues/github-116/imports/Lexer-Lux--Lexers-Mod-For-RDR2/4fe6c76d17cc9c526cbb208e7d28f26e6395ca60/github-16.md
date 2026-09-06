# GitHub #16: Bullet tracers

## Luminous-streak correction

The deployed `core/bullet_tracer` result produced no new visual language because
that PTFX is the vanilla smoke-like firearm trail. Moving another instance down
the synchronized path could only overlap or duplicate the trail the weapon
already emits. The user's report therefore invalidated the earlier conclusion
that this shipped effect was a suitable distinct tracer.

`modules/projectile_visibility.cpp` no longer loads, starts, moves, or removes
`core/bullet_tracer`. Mode 4 draws a configurable multi-corona incandescent
orange-red streak, with a bright moving head and fading tail, at the tracked
world-space shot position. Size, opacity, colour, tail length and segment count,
maximum distance, and matching point-light brightness/range are all INI-driven.
Mode 2 retains the old single-corona compatibility path.

The actual path correction remains valid: the streak starts from the equipped
weapon's `Gun_Muzzle` and follows the weapon entity's local +X barrel axis,
including alternating real weapon entities for dual wield. It does not use a
camera, eye, chest, screen-space, or HUD ray.

Issue-local static inspection confirmed there are no PTFX asset requests,
`bullet_tracer` starts, particle handles, or looped-particle cleanup calls left
in the isolated module. No build, install, or in-game claim was made.

Integration must replace the old block in `recon.cpp` with this module (the old
block still contains the duplicate smoke implementation), retain the existing
mode-4 dispatch/config selection, then build and install the combined ASI.
Acceptance must visibly show an orange-red moving streak distinct from the one
vanilla smoke trail, from the real muzzle for player and hostile shots, across
day/night, hipfire, aim, scopes, cover, horseback, dual wield, ranges, rapid
fire, and shotguns.

## Superseded muzzle-path implementation

Everything below records the earlier attempt and is not current integration
guidance; the luminous-streak correction above replaces its particle choice.

The existing moving `core/bullet_tracer` implementation did use Rockstar's
shipped particle, but its path was synthetic: it started at ped bone `7966`
(the right hand) and used gameplay-camera rotation for the player's direction.
That mismatch explained the reported second trail appearing to leave the
player's eyes. NPC trails were even less exact: they were aimed from the hand
toward the player's chest.

The isolated replacement in `modules/projectile_visibility.cpp` starts from the
equipped weapon entity's real `Gun_Muzzle` bone and follows the weapon's local
+X barrel axis. This convention is not guessed: Story Mode's
`ambush_exc_wagon_bomb.c` functions 508 and 509 resolve `Gun_Muzzle` and derive
the firing direction from
`GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS(weapon, 1, 0, 0)`. The path therefore
works in world space without a camera/HUD ray, including first person, scopes,
cover and mounted poses insofar as Rockstar orients the held weapon entity.
Story scripts query current held-weapon entity indices 0 and 1 together; the
replacement alternates distinct held entities so dual-wield shots originate at
both real muzzles rather than remaining pinned to the primary hand.
Firearm filtering remains in place, so thrown projectiles cannot create this
effect. The rejected corona remains compatibility-only and is not layered over
the selected particle mode.

Integration owns removing the old `VisibleProjectile` block from `recon.cpp`,
including `removeProjectileFx`, `clearVisibleProjectiles`, and
`updateProjectileVisibility`, then including `modules/projectile_visibility.cpp`
after `modules/items_casings.cpp` (it uses `casingItemForWeapon`) and before the
main loop. No dispatcher call changes are needed: the existing death cleanup and
per-frame `updateProjectileVisibility(ped, now)` calls keep their names.

The integrator should raise the selected particle defaults to
`ParticleScale=0.55` and `ParticleAlpha=1.0` for the requested daylight
legibility while retaining hot-reload adjustment. Remove the unused
`StreakLength` and `StreakWidth` globals/config reads once the old recon block is
gone; the particle implementation does not consume them.

No build, install, or in-game claim was made in this feature handoff. Acceptance
still requires checking one aligned trail (rather than a second eye-origin
trail), daylight and night visibility, hipfire, aimed fire, scopes, cover,
horseback, both dual-wield hands, several ranges, and shotguns.

## Returned-test correction: literal vanilla-only toggle and controls

The installed luminous-streak attempt was returned after the player saw no
tracer path and then received no answer to the requested settings questions.
Inspection established an important boundary: GameplayTweaks does not remove
Rockstar's weapon tracer records. `MyOverhaul/weapons.ymt` still matches all 58
non-empty `VfxWeaponTracerInfoHashName` assignments in the vanilla table (49
standard firearm entries and nine shotgun entries). Therefore an ASI toggle
cannot honestly claim to restore a removed or startup-loaded tracer hash.

The literal toggle now exists under `[Misc]`:

- `VanillaBulletTracersOnly=1` clears and disables GameplayTweaks' added tracer,
  leaving the preserved Rockstar weapon-data tracer as the only path;
- `VanillaBulletTracersOnly=0` allows the selected added renderer; and
- legacy `[ProjectileVisibility] Mode=off` remains an equivalent custom-renderer
  off switch.

This is a functional renderer gate, not a fabricated weapon-data hot switch.
It is reread within about one second. The added tracer now exposes and directly
consumes these settings:

- `Mode=luminous_streak|corona|off` selects the added renderer;
- `SizeMeters` controls head width and the tapering tail width;
- `Opacity` controls marker alpha from 0 to 1;
- `Red`, `Green`, and `Blue` control both marker and point-light colour;
- `TailLengthMeters` and `TailSegments` control luminous-streak geometry;
- `MaxDistanceMeters` controls renderer lifetime by travel distance;
- `Brightness` controls point-light intensity (chiefly visible at night); and
- `LightRangeMeters` controls that light's radius.

`ProjectileSpeed/GlobalFirearmSpeed` remains the tracer's travel speed because
the renderer must stay synchronized with the globally slowed firearm data. It
is a data-build setting requiring the projectile-speed patch/restart, not a
separate live cosmetic speed slider. A separate tracer speed would knowingly
detach the visual from the configured bullet path and was not invented.

LEXEDITOR's MISC settings group now exposes the vanilla-only toggle and all
added-tracer controls. The previous stale INI description claiming mode 4 moved
Rockstar's resident particle was replaced: mode 4 is the marker/light renderer,
and no PTFX request/start/move/remove calls exist in the issue module.

Static verification passed:

- `python tools/reverse-engineering/verify_projectile_visibility_issue_16.py`
- `git diff --check -- GameplayTweaks/modules/projectile_visibility.cpp
  GameplayTweaks/GameplayTweaks.ini editor/editor.html
  tools/reverse-engineering/verify_projectile_visibility_issue_16.py
  worklog/issues/github-16.md`

No build, install, game launch, GitHub mutation, or runtime-success claim was
made. After integration/install, acceptance is: set the Misc toggle to 1 and
confirm only the vanilla path remains; set it to 0 with luminous mode and verify
Size, Opacity, RGB, TailLength, TailSegments, MaxDistance, Brightness, and
LightRange each visibly affect the correct property without creating an
eye/camera-origin duplicate.

## Current actionable pass

The added tracer no longer guesses trajectory from the held weapon's local
axis. Each shooter keeps a pending muzzle sample and consumes a fresh
`GET_PED_LAST_WEAPON_IMPACT_COORD` readback to establish the actual muzzle-to-
impact path; stale/unbaselined samples are discarded rather than drawing a fake
line. `[ProjectileVisibility] Enabled` now directly controls the added renderer;
the confusing inverse Misc switch was removed. The issue verifier passes.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.
