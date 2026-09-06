# GitHub #43 — per-cartridge projectile speed

## 2026-08-06 implementation pass

LEXEDITOR gained a Weapons / Projectile speed subtab backed by the real
`CWeaponInfo/DamageModes/Item/AmmoInfo` relationships.  The extractor found 229
weapon/damage-mode relationships covering 69 cartridge records; no displayed
weapon-to-ammo relationship is inferred from a name.  Each cartridge has a
validated 0.05..10 multiplier over `ProjectileSpeed/GlobalFirearmSpeed`, an
effective-speed preview, and its actual weapon/damage-mode consumers.

Multipliers persist losslessly to
`GameplayTweaks/projectile_speed_multipliers.csv`.  The API rejects unknown,
duplicate, missing, nonnumeric, and out-of-range cartridge rows.  Default
balance differentiates high velocity, express/+P, explosive/incendiary,
shotgun, and arrow loads without changing weapon XML.

This pass deliberately remained partial.  The XML proves that `Speed` is one
field on `CWeaponInfo`, outside cartridge-keyed `DamageModes`; writing a
different speed into each cartridge would therefore be fake.  No proven native
changes a loaded weapon's projectile speed.  The editor explicitly reports
that the ASI runtime switch is not installed, and this issue must remain
Actionable until a real per-shot/runtime hook is implemented and observed in
game.  The visual tracer/marker speed is not used as a substitute for actual
projectile velocity.

Static checks passed: Python compilation, inline JavaScript compilation, all
229 mappings resolving to a present ammo record, 69-cartridge CSV round trip,
and `git diff --check` on the issue files.  No build, install, game launch, or
runtime test was performed by this feature agent.

## 2026-08-06 actionable follow-up

The live issue's prohibition on fake per-cartridge values is authoritative.
The prior UI was still editable and labelled `effective speed` while its own API
reported `runtimeSwitching: false`; persisting the CSV did not change projectile
physics. LEXEDITOR now keeps the 229 proven cartridge relationships visible for
research, but disables the inactive multiplier controls, removes their Save
button, labels them inactive, and shows the actual global runtime speed instead
of multiplier-derived preview numbers. The save API also refuses the inactive
configuration rather than claiming success.

A fresh source/native audit found one speed-taking primitive:
`MISC::SHOOT_SINGLE_BULLET_BETWEEN_COORDS(..., speed, ...)`. It creates a new
projectile; it does not alter or suppress the firearm's original shot. Using it
as a replacement would therefore require suppressing the real projectile while
preserving its exact muzzle trajectory, damage/falloff/penetration, impact and
challenge events, ammo debit, recoil, spread, Dead Eye behavior, shotgun pellet
count, arrows and special-ammo effects. No native supplies that interception.
Spawning a second bullet or zeroing damage on the first would duplicate
collision/events and is not a valid runtime switch.

The exact remaining blocker is an engine hook or a proven writable loaded
`CWeaponInfo.Speed` address that can be changed before each shot based on
`WEAPON::_GET_CURRENT_PED_WEAPON_AMMO_TYPE`. Without that hook, a weapon using
several cartridges still has one physical speed. No fake synthetic-bullet
implementation was added.

## 2026-08-06 resumed runtime audit

The live issue was reread before resuming work. It explicitly requires a real
runtime switch when one weapon supports multiple cartridges, so neither a
weapon-wide XML rewrite nor a second scripted bullet satisfies it.

The local ScriptHookRDR2 SDK exposes `getScriptHandleBaseAddress(handle)`, but
its `eGameVersion` enum recognizes only `VER_1_0_1207_60_RGS` and
`VER_1_0_1207_69_RGS`. Its own header warns that entity-field offsets vary by
patch. Consequently the older plan to walk
`weapon entity -> CObject -> m_pWeaponInfo -> Speed` cannot be implemented
safely on the current executable from this SDK alone: there is no current
version identity, proven object/weapon-info offsets, or signature for the
loaded `CWeaponInfo.Speed` field.

The native surface was checked again. `GET_PED_AMMO_TYPE_FROM_WEAPON` can select
the cartridge and `SHOOT_SINGLE_BULLET_BETWEEN_COORDS` accepts a speed, but the
latter only creates an additional bullet. `_SET_WEAPON_DAMAGE` is not a
projectile-speed setter. No native intercepts the firearm shot or returns its
mutable weapon-info record. A valid implementation therefore still requires
one of these engine-level prerequisites:

1. a current-build signature and validated pointer chain to the loaded
   `CWeaponInfo.Speed`, with restoration and per-shot synchronization; or
2. a current-build fire hook that can replace the original projectile while
   preserving Rockstar's ammo, recoil, spread, pellet, damage/falloff,
   penetration, impact/challenge, Dead Eye, arrow, and special-ammo behavior.

Without either prerequisite, writing runtime code would be an unguarded memory
patch or a behaviorally incorrect synthetic replacement. No such code was
added. The inactive editor controls and rejecting save API remain the honest
player-visible state.

## 2026-08-06 swarm recheck

The live issue and current checkout were audited again. No current-build
signature, weapon-object pointer chain, projectile-fire interception, or native
speed setter exists in the repository, shipped ScriptHookRDR2 SDK, or
decompiled Story scripts. The only speed-taking native remains
`SHOOT_SINGLE_BULLET_BETWEEN_COORDS`, which creates an additional projectile and
cannot preserve the original shot's complete behavior.

`tools/reverse-engineering/verify_projectile_speed_issue_43.py` now makes the
completed tooling boundary reproducible. It requires all 229 real
weapon/damage-mode relationships to resolve across 69 cartridge records,
requires the coherent default multipliers to serialize and reload losslessly,
and asserts both the disabled editor controls and client/server save guards
while runtime switching is absent. The verifier passed. Issue #43 remains genuinely engine-blocked on
the two prerequisites documented above; no unsafe offset guess or synthetic
second-bullet substitute was added.
