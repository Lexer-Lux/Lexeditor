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

The project file copies `SubModule.xml` and `GUI\Prefabs\**\*.*` into the deployed Bannerlord module folder after build.

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
