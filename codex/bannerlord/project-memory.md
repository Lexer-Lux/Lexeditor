# Project Memory

## Identity

This workspace is for a comprehensive Mount & Blade II: Bannerlord mod project. The current module is `LexerSkillTweaks`, a C#/.NET Framework 4.7.2 Bannerlord single-player module.

Current focus:
- Comprehensive Bannerlord skill overhaul with 20 custom skills grouped under four humor display buckets.
- Character screen should show the custom skills, skill cap 100, and quantitative effect lines with current values.
- MCM is the custom skill balancing panel; it edits the level 0 and level 100 values for the modded quantitative effects.
- Humor shifting is not designed yet. Custom XP sources and many perks now exist, but perks marked with `*` in `Design.txt` and the skill screen are still unimplemented.
- Recovery state as of 2026-06-12: the crash evidence points to early patching of `CharacterDeveloperHeroItemVM.InitializeCharacter`, whose method body references `CampaignUIHelper`. The deployed fix delays the character-screen Harmony patch until `OnGameStart` so `CampaignUIHelper` is not touched during module load.

## Local Paths

Workspace:
- `C:\Bannermod`

Bannerlord Steam install:
- `C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord`

Game bin:
- `C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\bin\Win64_Shipping_Client`

Deployed module:
- `C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\Modules\LexerSkillTweaks`

Deployed DLL output:
- `C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\Modules\LexerSkillTweaks\bin\Win64_Shipping_Client`

## Build

Build from `C:\Bannermod`:

```powershell
dotnet build
```

For an ordinary external `dotnet build`, the project file copies `SubModule.xml`, GUI assets, and non-runtime ModuleData assets into the deployed Bannerlord module folder after build. Lexeditor-hosted builds set `LexeditorSkipAssetDeploy=true`, so the cooperative template target skips those raw asset copies and Lexeditor performs non-binary deployment through its own staged/backup/rollback transaction instead.

## Dependencies

The module references Bannerlord assemblies from the game bin, plus these installed Bannerlord mod dependencies:
- `Bannerlord.Harmony`
- `Bannerlord.ButterLib`
- `Bannerlord.UIExtenderEx`
- `Bannerlord.MBOptionScreen` / MCMv5
- `RTSCamera` v5.3.25
- `RTSCamera.CommandSystem` v5.3.25
- `BattleMiniMap` v3.1.3

`SubModule.xml` currently depends on:
- `Native`
- `SandBoxCore`
- `Sandbox`
- `Bannerlord.Harmony`
- `Bannerlord.ButterLib`
- `Bannerlord.UIExtenderEx`
- `Bannerlord.MBOptionScreen`

`RTSCamera`, `RTSCamera.CommandSystem`, and `BattleMiniMap` are enforced by a runtime startup check in `src/SubModule.cs`, not as XML hard dependencies. They were briefly added to `SubModule.xml`, but that caused a startup crash in MCM/ButterLib service initialization on 2026-06-14, so they were removed from XML while remaining required by the mod design.

## Important Files

- `LexerSkillTweaks.csproj`: build/deploy paths and assembly references.
- `SubModule.xml`: Bannerlord module metadata and dependencies.
- `src/SubModule.cs`: module lifecycle entry point. It does not patch view-model classes during `OnSubModuleLoad`; it applies the character-screen patch during `OnGameStart`.
- `src/CustomSkillDefinitions.cs`: registers humor display buckets, custom skills, character-screen VM replacement, hidden vanilla XP blocking, and 100-level squished XP curve.
- `src/CustomSkillEffectRanges.cs`: default/configured quantitative ranges and character-screen effect text.
- `src/CustomSkillEffects.cs`: helper API for reading configured custom skill effect values.
- `src/CustomGameplayPatches.cs`: gameplay model hooks for implemented quantitative effects.
- `src/ExternalModPerkPatches.cs`: external mod integration gates. `Longview` unlocks Battle Mini Map display; `Eagle Eye` unlocks RTS Camera free camera. Other external-mod-backed perks remain starred until implemented.
- `src/LexerSkillTweaksSettings.cs`: MCM custom skill balancing panel.
- `src/SkillEffectPatch.cs`: disables hidden vanilla skill effects.
- `GUI/Prefabs/CharacterDeveloper/CharacterDeveloper.xml`: module-local character developer prefab override; extra-skills branch uses a four-column grid.
- `src/ModPaths.cs`: central module path helpers.
- `src/ModLog.cs`: logging helper.

## Generated Runtime Files

After launch/load, the deployed module may write:
- `ModuleData\custom_skill_effects.json`
- `LexerSkillTweaks.log`

These are expected in the deployed `Modules\LexerSkillTweaks` folder.

## Modding Notes

Bannerlord is a C#/.NET-heavy game, so decompilers such as dnSpy or ILSpy can inspect much of the practical gameplay logic from assemblies like:
- `TaleWorlds.CampaignSystem.dll`
- `TaleWorlds.Core.dll`
- `TaleWorlds.MountAndBlade.dll`
- `TaleWorlds.Library.dll`
- `SandBox.dll`
- `StoryMode.dll`

Prefer implementing changes as a normal Bannerlord module with C#, XML/data files, MCM, game-model overrides, campaign behaviors, and Harmony patches. Avoid editing base game DLLs directly.

## Working Conventions

- Keep changes scoped and compatible with Bannerlord's module loading model.
- Prefer existing project patterns before adding new abstractions.
- Use `rg`/`rg --files` for repo exploration.
- Use `dotnet build` for verification when code changes are made.
- Be careful around deployed files in the Bannerlord install; do not delete user/game files unless explicitly asked.
- Do not invent perk mechanics or XP-gain values without the user asking; those parts of the design are still open.

## Lexeditor Bannerlord Integration Invariants

As of 2026-09-12, the Bannerlord plugin uses these conservative rules. Keep them unless new game/upstream evidence establishes different behavior.

### Module metadata and dependency resolution

- Treat current BUTR `Bannerlord.ModuleManager` behavior as the interoperability reference for extended dependency metadata.
- Normalize BLSE `DependedModuleMetadatas`, legacy `LoadAfterModules`, and optional dependency blocks before native dependency rows. For duplicate load relations, the first row for a module ID wins; incompatibility relations use a separate first-ID-wins set. Existing compatibility-only legacy rows are structured-editable by ID/removal while retaining their original element shape and unknown attributes; creating new legacy rows stays source-only so Lexeditor does not invent a historical schema. Structured legacy saves carry the originally loaded valid-row identity baseline; if valid rows are added, removed, or renamed on disk, Lexeditor refuses the save until reload. Malformed blank-ID legacy elements remain unmanaged and preserved.
- Required extended dependencies may express `LoadBeforeThis` or `LoadAfterThis`; optional dependencies constrain ordering only when otherwise enabled and are not auto-enabled by Lexeditor Play.
- Reject contradictory declarations before graph resolution: loadable + incompatible for the same ID, both before + after for the same ID, BLSE incompatible rows carrying an ordering edge, and direct circular declarations.
- Native `DependentVersion` comparison follows TaleWorlds launcher semantics and ignores the changeset component. BLSE/BUTR community versions use minimum/wildcard/inclusive-range semantics.
- `RequiredGameVersion` is deliberately not modeled yet. Current ModuleManager compatibility code contains a legacy `SandBox` versus modern `Sandbox` ID ambiguity; do not let it affect Play until modern-game evidence resolves that ambiguity.

### Structured `SubModule.xml` writes

- Preserve unknown attributes, comments, unrelated XML nodes, and already-existing unusual order whenever a structured edit does not require changing them.
- When Lexeditor creates known structural sections, insert them in canonical relative order rather than appending after later sections.
- Newly-created `SubModule` records must contain required `Assemblies` and `Tags` containers even when empty.
- New modern `XmlNode` registrations require at least one `IncludedGameTypes/GameType`; never invent `Campaign` or another game type.
- Relation edits are preflighted as one proposed set before XML mutation. Invalid saves create no backup/temp file and make no partial edit.
- All structured writers remain contained to the selected project/module roots and detach predictable `.lexeditor.bak` / `.lexeditor.tmp` aliases before writing.

### Build and project handling

- Lexeditor-hosted builds pin `BannerlordDir`, `GameBin`, `ModuleDir`, and `OutputPath` to the selected Bannerlord installation/module so project-local values cannot redirect the standard hosted output paths.
- Lexeditor-hosted builds also pass `LexeditorSkipAssetDeploy=true`. The packaged `CopyModuleFiles` target honors that flag so non-binary assets are not raw-copied by MSBuild before Lexeditor can back them up and commit them transactionally. External `dotnet build` does not set the flag and retains the template's normal asset-copy behavior.
- This path pinning/skip convention is not a sandbox. `dotnet build` executes project-defined/imported MSBuild targets and tasks with the user's permissions. Build only trusted projects; arbitrary custom targets may ignore Lexeditor-specific properties.
- Structured `.csproj` property editing is intentionally non-evaluating: only a uniquely-defined, unconditional property is editable. Duplicate or conditional definitions remain visible but read-only, and backend saves reject them.
- Text-preserving `.csproj` edits ignore XML comments and CDATA when locating live property/`PropertyGroup` spans.
- If a workspace contains multiple top-level `.csproj` files, do not pick alphabetically. Require an explicit project selection and pass that exact filename through Build/property-save APIs.
- New Project creation is transactional across template copy, plugin initialization, and final project selection/validation. On failure, remove only the newly-created target directory and leave the registry/parent/siblings unchanged.
- Project registry temporary writes detach predictable helper aliases before writing; Rename restores the original folder if registry persistence fails.
- Create/Rename use portable Windows-safe folder-name rules even when Lexeditor runs on another platform.
- Bannerlord template display names must be escaped for XML contexts independently from the sanitized module/C# identifier.

### Deploy and runtime boundaries

- Asset deployment is additive and never intentionally deletes pre-existing deployed files as part of a successful sync. Overwrites get backups.
- Before the first deployed-file write, Lexeditor validates the complete source/destination/helper plan. All changed assets are staged to temporary files and all existing destinations are backed up before the first replacement.
- If a late destination replacement fails, already-committed existing assets are restored from backups and already-committed newly-created assets are removed; staged temporary files are cleaned up. Incomplete rollback is surfaced as an explicit error rather than silently reported as success.
- Runtime balancing files managed by the Runtime Overrides editor are excluded from ordinary build/deploy asset synchronization.
- Write-capable project/deploy paths reject resolved symlink/junction escapes. Read-only installed-module discovery remains compatible with legitimate mod-manager junctions where no write occurs.
- CI and isolated smoke tests establish editor/build/deploy behavior only; they do not establish real in-game runtime or visual acceptance. A local Bannerlord launch remains required for that final acceptance step.
