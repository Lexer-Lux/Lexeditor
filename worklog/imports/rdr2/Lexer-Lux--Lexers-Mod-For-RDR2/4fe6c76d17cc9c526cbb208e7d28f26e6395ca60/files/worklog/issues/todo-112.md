# Worklog: Todo 112

## #112 tracers — REVERTED, my regression

Replacing the nonexistent "MARKER_TYPE_CYLINDER" with the real 0x94FDAE17 made
the draw call work and exposed that the shape is a WORLD-VERTICAL cylinder: it
ignores the direction vector, so passing the tracer length as scaleZ produced a
multi-metre pillar on every shot, and on thrown dynamite because the projectile
path draws for those too. Draw removed; back to nothing rather than a pillar.
A marker cannot render an oriented streak at all. Three options written into
TODO #112 for Lexer to choose: engine per-weapon tracer, a particle trail on the
projectile, or a screen-space line. Not picking unilaterally again.

Installed AD28AD1DF15024139A3EEAF36A0ED775 (game was closed).


## #112 engine_tracer is a no-op and caused a regression — 2026-08-04

Build `9AE68E9DEC017FCD0A38CA5714A4091F66BD3A9DFE5D51DB2F448E0F02F07B6A`.

Counted `VfxWeaponTracerInfoHashName` in the pre-edit `weapons.ymt.disabled`:

    49  0xD5551261      <- standard bullet tracer, VANILLA ALREADY SETS THIS
     9  0x0C0B70A6      <- shotgun tracer, on WEAPON_EFFECT_GROUP_SHOTGUN

`ApplyProjectileSpeed.ps1` in `engine_tracer` mode writes `0xD5551261` onto every
firearm. So for 49 of 58 weapons it changed NOTHING (they already had it), and
for the 9 shotguns it REPLACED their correct shotgun tracer with the bullet one.
Net effect of the whole feature: no new visibility, plus a shotgun VFX
regression. That is why Lexer saw the coronas disappear and nothing replace them.

Reverted: the 9 `WEAPON_EFFECT_GROUP_SHOTGUN` records are back to `0x0C0B70A6`
(backup at `MyOverhaul/weapons.ymt.pre-tracer-revert`). Final counts verified
49/9, matching vanilla. `lml\MyOverhaul` is a JUNCTION to `C:\RDR2Mod\MyOverhaul`,
so project edits are live immediately — no copy step, and no separate install
hash to verify.

Conclusion for #112: assigning the tracer field is not the lever, because vanilla
already assigns it and RDR2 still shows no visible tracer. The lever is whatever
the hash POINTS AT, in the VFX data. `ApplyProjectileSpeed.ps1` should stop
offering `engine_tracer` until that is found, or it will silently redo this.

## #112 particle-trail choice — built and installed 2026-08-05

Lexer rejected engine-tracer mode because it merely re-selected the bullet
trail already assigned by vanilla, selected the world-space particle option,
and rejected a HUD overlay. `Mode=particle_trail` now requests the resident
`core` PTFX asset, starts one looped `bullet_tracer` effect for each detected
firearm shot, moves its world offset and rotation along the synchronized slow
projectile path, and removes it at end of flight. Only shooting peds enter the
path; thrown dynamite does not. `ParticleScale` and `ParticleAlpha` are exposed
for the visual test. The rejected corona remains an explicit fallback only.

Build passed with the two pre-existing C4838 warnings. Source and installed ASI
hash: `1B04C17793752D695333E6B8E740880958857528EEFC86FF78F087D9170CB26A`;
INI hashes matched. The game was running, so the loaded ASI was renamed aside
and the replacement will take effect on the next full restart. NOT VERIFIED IN
GAME: trail presence, alignment, scale, persistence and firearm-only filtering.
