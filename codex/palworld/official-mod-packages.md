# Palworld official mod-package mechanics

Source of truth reviewed 2026-09-09: Pocketpair's public `pocketpairjp/PalworldModUploader` repository.

## Supported boundary

The official loader shipped with the December 2025 Palworld v0.7 update. The documented Windows Steam client and Windows dedicated server loader discovers packages through an `Info.json` file under the Palworld Steam Workshop content root (Steam app `1623730`).

`Info.json` documents these top-level fields: `ModName`, `PackageName`, `Thumbnail`, `Version`, `DebugMode`, `MinRevision`, `Author`, `Dependencies`, `Tags`, and `InstallRule`.

Pocketpair's uploader requires `PackageName` to use only `[A-Za-z0-9]`, requires at least one `InstallRule`, accepts rule types `Lua`, `Paks`, `LogicMods`, `UE4SS`, and `PalSchema`, and requires each rule to contain at least one target.

## Loader behavior

`Mods/PalModSettings.ini` stores global enable state, `WorkshopRootDir`, and repeated `ActiveModList=<PackageName>` entries. At startup the loader examines Workshop packages and installs enabled packages according to `InstallRule`.

Documented install-type destinations:

| Type | Installed destination |
| --- | --- |
| `UE4SS` | `Mods/NativeMods/UE4SS` |
| `Lua` | `Mods/NativeMods/UE4SS/Mods/{PackageName}` |
| `PalSchema` | `Mods/NativeMods/UE4SS/Mods/PalSchema/mods` |
| `LogicMods` | `Pal/Content/Paks/LogicMods` |
| `Paks` | `Pal/Content/Paks/~WorkshopMods` |

`IsServer: true` creates a dedicated-server install rule. `DebugMode: true` forces uninstall/reinstall from the Workshop package every launch. Otherwise the loader compares `Version` as a plain string and reinstalls when the string changes.

Package-name collisions are unsafe: if multiple subscribed items use the same `PackageName`, only one is enabled and ordering is not guaranteed.

## Lexeditor design consequences

1. Treat an authoring project as an official package, not as an installed-game data directory.
2. Keep `Info.json` structured and preserve unknown future keys/rule members.
3. Keep package Targets relative and contained; Lexeditor must never permit `..`/absolute paths to turn a package rule into an arbitrary-filesystem write.
4. Do not invent PAK/Blueprint editing from the package schema. Those formats need their own evidence and round-trip tests.
5. Do not silently install/replace UE4SS. It is an official package type/runtime dependency with its own compatibility surface.
6. Deployment should ultimately target an explicit Workshop package/item directory and let Palworld's loader perform installation. Activation changes to `PalModSettings.ini` must be reversible and ownership-aware before Lexeditor claims them.

## References

- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/docs/en/01-General.md
- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/docs/en/02-Package.md
- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/docs/en/04-Tech.md
- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/MainWindow.xaml.cs
