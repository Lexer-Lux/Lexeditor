# GitHub #59 — editable binocular zoom levels

## Requested result

Regular and improved binoculars must have meaningfully different zoom, with an
editable FOV and a less oppressive binocular mask if the data supports it.

## Proven ownership

- Base `weapons.ymt` gives `WEAPON_KIT_BINOCULARS` the default scope component
  `COMPONENT_BINOCULARS_SCOPE01`.
- The base `CWeaponComponentScopeInfo` record for that component owns
  `LookingGlassFOV` (`5.735087`), `LookingGlassScale` (`1.000000`), the
  `w_binocular_inner01` mask model, and the `ScopeBinoculars` post-FX stack.
- Red Dead Offline's `WEAPON_KIT_BINOCULARS_IMPROVED` record points at the same
  `COMPONENT_BINOCULARS_SCOPE01`. Therefore the two items currently use the
  exact same optics definition; ordinary `WeaponCamera/CameraFov` is `50` on
  both and is not the distinguishing lens value.
- Rockstar's decompiled `binoculars.c` does not create or configure a scripted
  camera. In its active state it sets the `BINOCULARSINUSE` control context,
  exposes `INPUT_SNIPER_ZOOM`, and listens to `CAM::_0xDC62CD70658E7A02()` and
  `CAM::_0x796085220ADCC847()` for zoom-in/out sound events. The zoom range
  therefore belongs to the equipped looking-glass component, not that script.

Evidence files:

- `datasets/vanilla/weapons.ymt` (`WEAPON_KIT_BINOCULARS`)
- `_downloads/extract/update_1_common/common/packs/base/data/ai/weaponcomponents.meta`
- `_downloads/inspect-online-content/RDO/red_dead_offline/weapons/weapons_mp005_collector.ymt`
- `_downloads/RDR2-Decompiled-Scripts/script_rel/binoculars.c`

## Implementation prepared

`tools/reverse-engineering/apply_binocular_optics_59.py` performs narrow textual
edits rather than parsing and re-exporting either game-data file. It:

1. preserves the regular component and its vanilla `5.735087` FOV;
2. creates/updates `COMPONENT_BINOCULARS_SCOPE_IMPROVED` at `3.500000` FOV;
3. makes both overlay scales editable (the proposed first test is `0.900000`);
4. points only `WEAPON_KIT_BINOCULARS_IMPROVED` at the new component;
5. validates uniqueness and required fields before writing; and
6. is idempotent, so rerunning it updates the two records without duplicating
   the improved scope.

This targeted approach is intentional: a generic XML/YMT round trip could again
discard fields it does not understand, as happened in issue #199.

## Integration steps (integration agent only)

Run from the repository root:

```powershell
python tools/reverse-engineering/apply_binocular_optics_59.py `
  --components MyOverhaul/weaponcomponents.meta `
  --improved-source _downloads/inspect-online-content/RDO/red_dead_offline/weapons/weapons_mp005_collector.ymt `
  --improved-output MyOverhaul/weapons_mp005_collector.ymt `
  --regular-fov 5.735087 --improved-fov 3.5 --overlay-scale 0.90 --write
```

Then add this MyOverhaul replacement to `MyOverhaul/install.xml`:

```xml
<FileReplacement>
  <GamePath>update:/x64/pack_patch/mp005/data/ai/weapons_mp005_collector.ymt</GamePath>
  <FilePath>weapons_mp005_collector.ymt</FilePath>
</FileReplacement>
```

Rebuild generated knowledge indexes, run the normal data/static suite, install
MyOverhaul, and hash-verify the installed files. The feature agent did not edit
the shared component table or installer and did not build/install.

## Static validation

- Dry-run against the current authoritative component table and the installed
  RDO source succeeded.
- Write-mode was run twice on temporary copies. The result contained exactly
  one regular scope (`FOV 5.735087`, scale `0.900000`), exactly one improved
  scope (`FOV 3.500000`, scale `0.900000`), and the improved weapon referenced
  only the new component on both runs.
- `python -m py_compile tools/reverse-engineering/apply_binocular_optics_59.py`
  passed.
- `git diff --check` passed for the new tool.

## Runtime boundary / acceptance

This is proven data ownership but not in-game acceptance. After integration,
Lexer must confirm:

1. regular binocular zoom remains recognizably vanilla;
2. improved binoculars zoom farther and native zoom controls/sounds still work;
3. the `0.90` mask scale is less oppressive without exposing broken edges or
   clipping; and
4. the rest of the RDO collector weapon file still behaves normally.

`LookingGlassFOV` and `LookingGlassScale` are startup-loaded data, so an ASI INI
cannot safely change them after load without an unproven memory patch. The safe
editable interface in this pass is the patcher's numeric arguments (restart
required), not live INI zoom steps. A LEXEDITOR control can wrap those same
fields later. A custom scripted-camera overlay was rejected because it would
replace rather than retune Rockstar's native looking-glass path and had no
runtime proof.

## Returned-test correction

The first installed optics build did not make the Online-only improved
binocular item obtainable in Story Mode. The player's feedback therefore could
not exercise the requested regular/improved comparison. The runtime now reads
`Binoculars.UnlockImproved` (default `1`), grants the imported improved kit once
the live player ped exists, and logs the resulting weapon/inventory ownership.
The issue remains actionable until that acquisition path is built, installed,
and the improved kit is visibly available in the item wheel.

## 2026-08-06 returned-test fix: real Story inventory path

The weapon-only `GIVE_WEAPON` attempt did not answer the player's question:
there was still no obtainable/selectable improved-binocular item in Story Mode.
The fix now imports the missing catalog and wheel layers rather than treating an
internal weapon handle as acquisition:

- `catalog_sp.ymt` contains a Story `WEAPON_KIT_BINOCULARS_IMPROVED` item using
  the imported `W_BINOCULARS02` model and its `INVENTORY_ITEMS_MP` icon;
- `quickselectitems.ymt` gives it a distinct native `KIT` entry after regular
  binoculars, so the two can be selected and compared in the item wheel;
- `strings.gxt2` supplies the Story name and description; and
- the unregistered issue module `binocular_optics.cpp` calls `INVENTORY_ADD`,
  separately ensures weapon ownership, verifies both states, and retries failed
  acquisition every five seconds. This specifically replaces the rejected
  one-shot weapon-only grant.

The existing optics split remains: regular `LookingGlassFOV=5.735087`, improved
`3.500000`, both mask scale `0.900000`. Static checks passed:

- `python tools/reverse-engineering/verify_binocular_optics_issue_59.py`
- catalog and quickselect XML parse; and
- Python verifier/build helpers compile.

Integration must include and call `updateImprovedBinocularAccess(ped, now)`,
then build/install. Runtime acceptance is now possible: select regular and
improved binoculars separately in the native Kit wheel, confirm improved zooms
farther, and confirm the reduced mask exposes no broken edge.

## 2026-08-06 live acquisition failure and Story-table fix

The live log disproved the claim that the imported item was accessible. Every
five-second attempt returned `addReturned=0`, `inventory=0`, and `hasWeapon=0`.
The catalog and quickselect rows were present, but the weapon definition lived
only in the Online `mp005` table; replacing that pack file did not register the
weapon in the loaded Story weapon table.

The exact patched `WEAPON_KIT_BINOCULARS_IMPROVED` `CWeaponInfo` record and its
distinct `0x246BA454` slot-navigation entry are now imported into the existing
full `MyOverhaul/weapons.ymt`, which already replaces Story's base weapons
table. The narrow importer preserves the rest of that heavily modified file and
is idempotent. Ownership is accepted when either the Story inventory item or
the weapon is confirmed, rather than demanding both representations.

On confirmed ownership, the game now posts the location itself:
`Improved Binoculars added - Item Wheel > Kit; cycle binoculars`.
The imported item uses the regular binoculars' proven resident Story icon
(`INVENTORY_ITEMS/WEAPON_KIT_BINOCULARS`) instead of depending on the Online
inventory dictionary merely for a different picture.

## Returned test: imported Online item does not enter the Story binocular script

Lexer confirmed that Improved Binoculars appeared in the item wheel but that
selecting them did nothing. The shipped `binoculars.c` explains the exact
failure: its state machine compares the equipped item to
`WEAPON_KIT_BINOCULARS` throughout and contains no reference to
`WEAPON_KIT_BINOCULARS_IMPROVED`. Catalog, quick-select, inventory ownership,
animation lookup, and a separate scope component cannot make a different weapon
hash pass those script gates. The previous claim that the imported item was an
accessible test vehicle was wrong.

There is no corresponding limitation on changing the regular binoculars. They
already point to `COMPONENT_BINOCULARS_SCOPE01`, whose `LookingGlassFOV` is the
same optics field previously changed only on the unusable imported item. The
authoritative regular component is now `3.500000` instead of vanilla
`5.735087`; Rockstar's native `INPUT_SNIPER_ZOOM` state machine remains intact,
so this retunes the absolute FOV of the regular binocular zoom path rather than
inventing a second control or scripted camera. The reduced `0.900000` mask scale
is retained. The unused improved record is `2.500000` so it remains distinct if
Story support is ever implemented, but it is not the acceptance path.

`binocular_optics.cpp` no longer grants or advertises the dead Online item. Its
registered entry point now samples the working regular-binocular aim camera and
logs `GET_FINAL_RENDERED_CAM_FOV` plus
`GET_FIRST_PERSON_AIM_CAM_ZOOM_FACTOR` whenever a native zoom level changes.
Those values provide runtime evidence of the actual levels instead of treating
item ownership as optics proof.

Integration also removed the stale quick-access preference/grant for
`WEAPON_KIT_BINOCULARS_IMPROVED`. Q/RB now selects only the regular kit accepted
by Story's `binoculars.c`; no path in GameplayTweaks advertises or equips the
dead Online hash.

Static acceptance is
`python tools/reverse-engineering/verify_binocular_optics_issue_59.py`. Runtime
acceptance still requires a restart, then using ordinary Story Binoculars from
Item Wheel > Kit: the view must be visibly tighter than vanilla, native zoom
in/out and sounds must still step normally, the log must record changing camera
values, and the 0.90 mask must have no exposed edge. No build, install, game
launch, label change, or runtime-success claim was made in this source pass.

## Returned test: missing mask and unverifiable zoom steps

The installed test showed no useful side obstruction, and a log-only FOV sample
did not let the player compare zoom levels while playing. GameplayTweaks now
draws a curved, ASI-owned side mask whenever the regular binocular aim camera is
active. `[Binoculars] MaskScale` hot-reloads; larger values expand the clear
opening and cover less of the screen. `MaskOpacity`, `MaskEnabled`, and
`ShowZoomReadout` hot-reload on the same approximately two-second cadence.

The readout displays current rendered FOV, magnification relative to the
weapon's 50-degree camera baseline, the native zoom factor, and the configured
optics-data comparison (`3.50`, vanilla `5.74`). This makes native zoom-step
changes visible without relying on memory or a log file.

The underlying `LookingGlassFOV` zoom range remains startup-loaded weapon data.
No safe native setter exists for the active first-person aim camera, so the INI
does not falsely claim to hot-reload that range. Changing the actual base range
still requires editing/installing `weaponcomponents.meta` and restarting; the
new readout makes the result directly observable after that restart.

## Returned request: editable restart-applied zoom

The lack of a live camera setter does not prevent an INI setting. `[Binoculars]
OpticsFOV` now owns the regular Story binocular component's startup FOV (range
1.00-20.00; lower is stronger). On config load/hot reload, GameplayTweaks
narrowly updates only `COMPONENT_BINOCULARS_SCOPE01/LookingGlassFOV` in the
active junctioned `lml/MyOverhaul/weaponcomponents.meta`, using a temporary file
and atomic replacement. Rockstar consumes that materialized value on the next
game launch. The on-screen readout uses the configured value instead of a
hard-coded `3.50`.

Rockstar exposes one base `LookingGlassFOV`, not independent data values for
each native zoom notch; its existing zoom state machine derives the selectable
levels. `MaskScale`, `MaskOpacity`, and the ASI mask remain live controls.

## Correction: independently editable stages

The preceding `OpticsFOV` control did not meet the request: it moved the whole
native range rather than setting each stage. Runtime evidence recorded three
actual Story stages (`22.62`, `15.19`, and `8.58` rendered FOV), and Rockstar's
Online `binoculars.c` independently proves a three-position index driven by
`INPUT_SNIPER_ZOOM_IN_ONLY` and `INPUT_SNIPER_ZOOM_OUT_ONLY`.

GameplayTweaks now owns those two stage controls while binocular aim is active
and renders a camera synchronized every frame to the underlying gameplay-camera
position and rotation. `[Binoculars] ZoomStage1FOV`, `ZoomStage2FOV`, and
`ZoomStage3FOV` independently set the scripted camera FOV and hot-reload. The
readout identifies the selected stage and its actual rendered FOV. Leaving
binocular aim, disabling `CustomZoomStages`, or losing the binocular weapon
immediately stops and destroys the scripted camera.

This is compiled/static work until the camera is confirmed to track look input,
cycle all three values in both directions, and restore ordinary gameplay camera
control cleanly in game.

## Returned test: scripted stages rejected

The in-game test failed both required behaviors. Zoom-stage input produced no
visible change, and the scripted camera rendered from behind the physical
binocular model, leaving both eyepieces hanging across the view. The attempt was
disabled live and removed from source. `CustomZoomStages` and the three false
stage settings are no longer advertised.

The native binocular camera, native zoom controls, ASI side mask, and readout
are restored. Independent stage values remain unsolved: the data supplies only
one `LookingGlassFOV`, while replacing the rendering camera is not acceptable
without a proven way to reproduce Rockstar's looking-glass camera transform.
