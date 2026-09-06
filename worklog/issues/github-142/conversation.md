# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356293946 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/142

Created: 2026-08-06T02:24:14Z; updated: 2026-09-05T06:57:09Z

Exact metadata: [source record](sources/issue-5356293946-9b15bd23044066e7ddd360188f4c225feef4d3d611dba21327f2722a2987e3a4.json).

Okay, so it seems like the +Damage +Range effect tags on ammo items are just for show, kind of like the displayed weapon stats -- the actual effects and damage are done in the weapons tab? Make an ammo subtab in weapons in LEXEDITOR that lets me customize those values. Add to it a velocity value so I can give +P rounds more velocity and shit. No, make it a multiplier. Of the base value. Which will be an .ini value. In the dev values section. Which we have something similar already, so IG we'll just be making a way of overriding htat with a multiplier on a per-catridge basis.

PER-CARTRIDGE PROJECTILE-SPEED TOOLING AND BALANCE — extend Lexer-Lux/Lexeditor#208's global
     speed setting into per-cartridge tooling. Map every weapon/damage-mode to
     its real ammunition family and expose editable speeds per cartridge
     (caliber, regular/express/high-velocity/split-point, +P, explosive, shotgun
     loads, arrows, specials), then set coherent defaults. If a weapon supporting
     several cartridges can't actually vary speed per cartridge, build the
     runtime switch rather than showing me fake per-cartridge values.

## issue 5356293946 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/142

Created: 2026-08-06T02:24:14Z; updated: 2026-09-06T13:17:14Z

Exact metadata: [source record](sources/issue-5356293946-e00bb4cab02909fa39189df9ef8887d47a2d976b6ac8203ef48612add7f35a53.json).

**Status: Not implemented with the currently proven approach.** Static weapon/ammunition mappings do not provide independent live projectile speed for every cartridge. The later mapping audit also found omitted patch weapons. Closing records the technical blocker, not a completed velocity feature.

## issue 5356293946 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/142

Created: 2026-08-06T02:24:14Z; updated: 2026-09-06T13:57:23Z

Exact metadata: [source record](sources/issue-5356293946-fedbf5c3683504e1e578eebb724514f63f67f86acb756202130358e44624f98e.json).

**Status: Not implemented with the currently proven approach.** Static weapon/ammunition mappings do not provide independent live projectile speed for every cartridge. The later mapping audit also found omitted patch weapons. Closing records the technical blocker, not a completed velocity feature.

## comment 5550121053 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/142#issuecomment-5550121053

Created: 2026-08-06T08:29:40Z; updated: 2026-08-06T08:29:40Z

Exact metadata: [source record](sources/comment-5550121053-650c3856a788172294bb98bf177875311033cd65e61efa46586decbd85d5da28.json).

Partial implementation landed in LEXEDITOR: 69 cartridges and 229 weapon/damage-mode relationships are mapped with validated per-cartridge multipliers and effective-speed previews. The API is live and reports `runtimeSwitching: false`. No proven runtime projectile-velocity setter exists yet, so this remains `actionable`; tracer visual speed is not being misrepresented as projectile physics.

## comment 5550121071 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/142#issuecomment-5550121071

Created: 2026-08-06T10:42:28Z; updated: 2026-08-06T10:42:28Z

Exact metadata: [source record](sources/comment-5550121071-009492584858454bec44ca34cec54818a776a75730742f4650e0551735cd0516.json).

Swarm re-audit completed. LEXEDITOR now maps 229 real weapon/damage-mode entries across 69 cartridge records and refuses to save inactive fake controls. A safe runtime switch still requires either a current-build CWeaponInfo.Speed signature/pointer chain or a firearm-shot interception hook; the available bullet native only adds a second projectile and cannot preserve original shot semantics. Moving this to needs a human rather than shipping a false per-cartridge control.

## comment 5550121077 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/142#issuecomment-5550121077

Created: 2026-08-06T13:30:48Z; updated: 2026-08-06T13:30:48Z

Exact metadata: [source record](sources/comment-5550121077-ffb2b91029bda1ef81168c0498e983a35c05540ace7bf006b9756360235daa8b.json).

I'm so confused right now. If you can't change bullet speed then how do we have a working bullet speed control already? 

## comment 5550121084 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/142#issuecomment-5550121084

Created: 2026-08-09T07:37:05Z; updated: 2026-08-09T07:37:05Z

Exact metadata: [source record](sources/comment-5550121084-eb7dd024ab863562f77b897e59d38a45f3de8f076b677ca3b3447d57c24d4ca0.json).

Second-pass research reconciles the existing working global control with the per-cartridge blocker.

The global control is real but build-time: `ApplyProjectileSpeed.ps1:24-69` rewrites direct `CWeaponInfo/Speed`, then requires data deployment/restart. Lexer’s in-game confirmation is recorded in `codex/runtime-engine-limits.md:77-90`. Per-cartridge schema differs: Schofield’s five cartridge-keyed `DamageModes/Item/AmmoInfo` entries are at `datasets/vanilla/weapons.ymt:59259-59395`, while its one shared `Speed` sits outside `DamageModes` at line 59484.

The 69 mapped ammunition records split into 28 ordinary firearm `CAmmoInfo` records with no speed field, plus 13 `CAmmoProjectileInfo` and 28 `CAmmoThrownInfo` records with cartridge-owned `LaunchSpeed`. Arrows/thrown/special projectiles can therefore receive honest restart-time per-cartridge controls; ordinary firearm loads require runtime switching of weapon-owned speed.

Resolved native boundary: `GET_PED_AMMO_TYPE_FROM_WEAPON` is `0x7FEAD38B326B9F74`; `SHOOT_SINGLE_BULLET_BETWEEN_COORDS` is `0x867654CBC7606F2C` and creates a second projectile. The SDK exposes no weapon-speed setter. Installed RDR2 is 1.0.1491.50, while the SDK offset table recognizes only 1207.60/1207.69 and warns offsets change by patch. A current-build signature/pointer chain or semantics-preserving firearm-shot hook is still required.

New defect: the global helper matches only literal `<FireType>BULLET</FireType>`. Seven patch weapon records store the schema-resolved bullet type as raw `0x0A8AE350` and retain `Speed=2000`, so M1899, Evans, LeMat, Gambler, Navy, Navy Crossover, and Elephant Rifle are currently skipped.

No runtime firearm multiplier or label change was made. Current-build reverse engineering remains required before ordinary firearm cartridge multipliers can ship.

## comment 5550121098 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/142#issuecomment-5550121098

Created: 2026-08-11T07:13:33Z; updated: 2026-08-11T07:13:33Z

Exact metadata: [source record](sources/comment-5550121098-19ee14ada3712ef8e81f50621fa6550211197d3cdef0fc5d6c1c31f75421d58d.json).

New re-audit finding: the Projectile Speed page does not map the complete weapon stack. It loads only base `weapons.ymt`, although the editor also defines six weapon patch files.

The base file has the reported 229 weapon/ammo relationships. The patch files add seven weapon records and 32 relationships: M1899 5, Evans 5, LeMat 6, Gambler Double-Action 5, two Navy records 10, and Elephant Rifle 1. Their names are stored as hashes in the patch files.

Player impact: these seven records do not appear in the editor mapping. A later runtime switch built from the present list would not apply cartridge multipliers to them. The complete static target is 261 relationships, with the patch hashes resolved before display or save.

This is separate from the global helper defect already reported. No runtime firearm-velocity method was found, so the physical-speed blocker remains.
