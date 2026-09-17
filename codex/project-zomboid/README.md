# Project Zomboid

Settled Project Zomboid knowledge used by the Lexeditor plugin. Keep implementation progress and failed experiments out of this file.

## Supported boundary

The initial plugin targets the current Windows Steam Build 42 stable family (Steam app `108600`). At the start of this plugin work on 2026-09-12, the official stable release was 42.20.4. The first structured script schema references are the 42.20.x PZ API Docs, so Lexeditor fails closed instead of assuming undocumented fields or layouts.

Install discovery requires `ProjectZomboid64.exe`, `media/scripts`, and the current Build 42 generated-script tree at `media/scripts/generated`. The generated tree is used as a conservative current-Build-42 discriminator so a legacy install is not accepted merely because it has the executable and older script directory.

The installed Steam directory is source/runtime material and is not an editor-save destination. Authoring happens in a separate mod project. Local acceptance deployment uses Project Zomboid's native user mod directory rather than rewriting installed game files.

## Build 42 mod layout

Build 42 mods are version-aware. Lexeditor models a project with `common/` plus a `42/` version folder. The version folder carries its `mod.info` beside `media/` content. Local test deployment copies the complete project under the user's `Zomboid/mods/<project>/` folder.

Project Zomboid itself owns activation and ordering. `mod.info` exposes dependency/order metadata including `require`, `incompatible`, `loadModAfter` and `loadModBefore`. Lexeditor does not invent a second runtime loader or claim semantic merge behavior between independent mods.

## `mod.info`

The editor models scalar fields documented for Build 42, including `name`, `id`, `author`, `modversion`, `description`, `icon`, `url`, `versionMin`, `versionMax`, dependency/order fields, and `category`.

Unknown keys, repeated non-edited keys, comments and other unmodeled lines must be preserved. A write is rejected if the file hash changed after it was read. `name` and `id` are treated as required for Lexeditor-created projects. Version bounds use explicit build-major forms such as `42.20` or `42.20.4`.

## Current ZedScript families

The current `pz-scripts-data` registry identifies these Build 42 script families at module level: `animationsMesh`, `craftRecipe`, `entity`, `evolvedrecipe`, `fixing`, `fluid`, `item`, `mannequin`, `model`, `sound`, `timedAction`, and `vehicle`. Lexeditor structurally inventories these top-level records while deliberately ignoring similarly shaped text inside comments, quoted strings, and nested blocks.

Recognition is not the same as editability. Animation meshes, items, evolved recipes, conservative typed craft-recipe fields, `fixing`'s typed `ConditionModifier`, top-level fluid scalars, a conservative vehicle scalar subset, conservative module-level sound scalars, conservative module-level model scalars, conservative module-level mannequin scalars, and `timedAction`'s independently typed `actionAnim` are currently structured. Only `entity` remains family-level read-only: its current schema leaves its scalar attributes untyped, and the current `GameEntityScript` Java API does not independently expose those attributes with enough type/semantic information to justify a writer. Nested, repeated-list, and compound substructures in otherwise structured families may also remain read-only. The narrow `fixing`, `mannequin`, and `timedAction` boundaries are documented separately in this codex.

## `animationsMesh`

The current script schema lists `animationDirectory`, `animationPrefix`, `keepMeshAnimations`, `meshFile`, and `postProcess` but leaves their types unspecified. Project Zomboid's current Java API provides the missing type evidence: `keepMeshAnimations` is a boolean, `meshFile` and `postProcess` are strings, while animation directories and prefixes are stored as repeated string lists.

Lexeditor therefore edits only existing module-level `keepMeshAnimations`, `meshFile`, and `postProcess` properties. Repeated `animationDirectory` and `animationPrefix` entries remain read-only and byte-preserved rather than being flattened into a scalar field or rewritten with guessed list semantics. The editor reports their occurrence counts so the preserved list structure remains visible.

As with the other conservative adapters, stale files, missing edited properties, duplicated editable properties—including same-line duplicates—and malformed boolean/script-punctuation values fail closed. Unknown fields and repeated animation source entries remain untouched.

## Item blocks

Build 42 items use required `ItemType` values from this finite set:

- `base:alarmclock`
- `base:alarmclockclothing`
- `base:animal`
- `base:clothing`
- `base:container`
- `base:drainable`
- `base:food`
- `base:key`
- `base:literature`
- `base:map`
- `base:moveable`
- `base:normal`
- `base:radio`
- `base:weapon`
- `base:weaponpart`

The item writer edits only existing top-level scalar properties that are firmly documented and can be patched without rebuilding the block: `ItemType`, `Weight`, `Icon`, and `DisplayCategory`. `Weight` is a float with a documented minimum of `0.0`. `Icon` names resolve to item textures under `media/textures/` according to Project Zomboid's item-icon conventions. `DisplayCategory` is a translation-backed inventory category.

Nested `component` blocks and unknown item properties are preserved. Comments and quoted strings are ignored when locating structural braces. If an edited property is duplicated or missing, the writer refuses the change rather than guessing where to insert/resolve it.

## `evolvedrecipe`

The current Build 42 schema documents `AddIngredientIfCooked`, `AddIngredientSound`, `BaseItem`, `CanAddSpicesEmpty`, `Cookable`, `MaxItems`, `MinimumWater`, `Name`, `ResultItem`, and `Template`.

Lexeditor patches only properties that already exist. `AddIngredientIfCooked` and `CanAddSpicesEmpty` are booleans. `MaxItems` is an integer with minimum 1. `MinimumWater` is finite numeric data. `BaseItem` and `ResultItem` use full item references. `Cookable` is unusual: the current schema documents it as presence-only, and explicitly notes that `Cookable = false` does not disable it. Therefore Lexeditor never writes false into that property; removing the property would need a separate structural operation.

## `craftRecipe`

Build 42's current crafting family is `craftRecipe`, not the older legacy `recipe` shape. A craft recipe commonly contains nested `inputs` and `outputs` blocks. Lexeditor preserves those blocks byte-for-byte and edits only existing top-level fields whose current schema supplies enough type information to validate independently:

- `AllowBatchCraft` and `CanWalk` — booleans;
- `ResearchSkillLevel` and `time` — integers;
- `tags` — semicolon-separated tag names;
- `AutoLearnAll`, `AutoLearnAny`, and `SkillRequired` — semicolon-separated `skill:integer` maps;
- `category` and `Tooltip` — translation-backed scalar keys;
- `Icon` and `timedAction` — scalar identifiers/references.

The skill-map writer validates pair syntax and integer values and rejects duplicate skill keys case-insensitively. Documented property-name casing variants such as `Time`/`time` and `Tags`/`tags` are recognized without rewriting the spelling already present in the source. Duplicate editable properties—including case-only or same-line duplicates—fail closed.

Callbacks, `inputs`, `outputs`, mappers, `xpAward`, and other under-typed or compound data remain read-only until their mutation grammar is independently grounded. A file containing those fields can still be edited safely because all unmodeled bytes/text are preserved and writes target only existing top-level property spans.

## `fluid`

The current Build 42 `fluid` schema has two simple module-level scalar properties suitable for surgical editing: `ColorReference` and `DisplayName`. `DisplayName` is a translation key; `ColorReference` names the color reference used by the fluid.

The behavior-bearing fluid data is nested in child blocks such as `Properties`, `Categories`, `BlendWhiteList`, `BlendBlackList`, and `Poison`. Those child blocks are deliberately read-only. The fluid writer changes only an existing top-level scalar property span, rejects missing or duplicated edited properties, and preserves every child block and unknown field verbatim.

## `vehicle`

Vehicle scripts combine a large top-level parameter surface with substantial nested structure (`part`, model/area/passenger/wheel-style blocks and related data). Lexeditor therefore exposes only a small current-schema subset that can be validated and patched without rebuilding the vehicle:

- floats: `animalTrailerSize`, `engineForce`, `engineIdleSpeed`;
- integers: `engineLoudness`, `engineQuality`, `engineRepairLevel`, `gearRatioCount`;
- booleans: `hasLighter`, `isSmallVehicle`;
- scalar identifiers/text: `carMechanicsOverlay`, `carModelName`, `engineRPMType`.

All nested vehicle blocks, array-valued fields, templates, textures, physics geometry, ratios beyond the explicitly modeled count, and other unmodeled parameters remain read-only and byte-preserved. As with the other script adapters, Lexeditor only edits properties already present and rejects stale, missing, duplicated, malformed, or out-of-scope edits instead of synthesizing structure.

## `sound`

Module-level Build 42 `sound` records expose a small typed scalar surface that can be patched without rebuilding their clip data:

- `category` — scalar text;
- `is3D` and `loop` — booleans;
- `master` — one of `Primary`, `Ambient`, `Music`, or `VehicleEngine`;
- `maxInstancesPerEmitter` — integer.

Audio sources and playback details live in nested `clip` blocks, including fields such as file path, minimum/maximum distance, reverb factor, and volume. Those clip blocks remain read-only and are preserved verbatim. The structured editor is deliberately limited to module-level `sound` records; sound-shaped child blocks inside vehicles or templates are not promoted to independent editable records.

As elsewhere, the writer changes only properties already present. Stale files, missing properties, duplicate edited properties, invalid booleans, undocumented `master` values, and malformed integers fail closed rather than causing structural insertion or normalization of unrelated sound data.

## `model`

Build 42 models can exist at module level and as nested vehicle/part structures. Lexeditor deliberately structures only module-level model records and only the explicitly typed scalar properties that can be validated without interpreting model assets:

- `cullFace` — `Back`, `Front`, or `None`;
- `invertX`, `static`, and `undoCoreScale` — booleans;
- `scale` — finite float;
- `postProcess` and `shader` — scalar strings.

Mesh and texture paths, model/animation block references, colors, transforms, bone weights, vehicle/part-local model blocks, and nested attachment blocks remain read-only. In particular, an attachment's offsets and rotations are preserved byte-for-byte when a top-level model scalar changes.

The model writer only replaces existing top-level property spans. Missing or duplicated edited properties, stale files, malformed booleans, invalid culling modes, non-finite scales, and script punctuation fail closed; Lexeditor does not synthesize model structure or normalize unmodeled asset references.

## Filesystem portability

Project APIs expose project-relative paths with forward slashes. On Windows the same file can be surfaced through case-insensitive or alias-equivalent filesystem spellings, so script discovery resolves paths and compares normalized filesystem identities before authorizing a save. Linux remains case-sensitive. The cross-platform CI matrix exists specifically to keep this containment behavior honest.

## Deployment safety

Lexeditor stages a full local-mod copy before replacing an existing Lexeditor-owned deployment. The project records hashes of every deployed file. Redeploy/remove is allowed only while the target still exactly matches the recorded deployment. An unowned folder or any external modification—including an added foreign file—causes refusal instead of overwrite/removal.

The deployment-state file is not treated as authority to traverse an arbitrary path. Its recorded target must first equal the currently expected `<user-root>/mods/<project>` target. A forged or stale target outside that location is reported as undeployed/unowned and is never tree-hashed or removed. The installed-game preflight passes its explicit `--user-root` into this same validation instead of relying on process-global environment state.

Symlinks are refused in this deployment path, including replacement of the deployed root with a link after deployment. Lexeditor state/temp files are not copied into the game-visible mod. Clean owned deployments can be replaced transactionally and removed completely; foreign, linked, changed, or state-tampered deployments are deliberately left untouched for the user to reconcile.

## Research references

- Official Project Zomboid release/status pages — current stable build boundary.
- Official Project Zomboid Java API, including `zombie.scripting.objects.AnimationsMesh`: <https://projectzomboid.com/modding/zombie/scripting/objects/AnimationsMesh.html>
- Official Project Zomboid Java API `GameEntityScript`: <https://projectzomboid.com/modding/zombie/scripting/entity/GameEntityScript.html>
- PZ Wiki Modding / PZ API Docs: <https://github.com/PZ-Wiki-Modding/PZ-API-Docs>
- PZ Wiki Modding / ZedScripts: <https://github.com/PZ-Wiki-Modding/ZedScripts>
- PZ Wiki Modding / pz-scripts-data: <https://github.com/PZ-Wiki-Modding/pz-scripts-data>
- JCPaezD / project-zomboid-hosted-toolkit — current Windows Build 42 client-mod-list reference (`Zomboid/mods/default.txt`): <https://github.com/JCPaezD/project-zomboid-hosted-toolkit>
- Twynzen / pz-forge-live — Build 42.20 local-mod deployment and existing-save `mods.txt` reference: <https://github.com/Twynzen/pz-forge-live>

These references supply format/schema/runtime knowledge; no third-party parser source, schema dataset, or mod-manager implementation is vendored into Lexeditor.
