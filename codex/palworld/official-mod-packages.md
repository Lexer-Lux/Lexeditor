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

Package-name collisions are unsafe: if multiple Workshop packages use the same `PackageName`, only one is enabled and ordering is not guaranteed.

## Pocketpair local test-package convention

The official Palworld Mod Uploader has an explicit development shortcut: **Shift + Create New Mod** bypasses Steam Workshop registration and creates a local package folder under the Workshop content directory. Pocketpair documents this as useful for debugging/testing because no Steam upload is required.

The uploader source marks this path as a Shift-click bypass and allocates a **random 10-digit directory name**. The resulting package has no Steam PublishedFileId and cannot be uploaded directly with the uploader; to publish it, the author must create/register a normal Steam-backed item and move the package content there.

This is materially different from a subscribed/published Workshop item:

- the 10-digit folder is local development state, not a Steam item Lexeditor should pretend to own remotely;
- it is a legitimate place for the official loader to discover a package during local testing;
- publication/registration remains Steam/Pocketpair-uploader behavior;
- activation still belongs to the official loader / Palworld Mod Management UI.

## Lexeditor design consequences

1. Treat an authoring project as an official package, not as an installed-game data directory.
2. Keep `Info.json` structured and preserve unknown future keys/rule members.
3. Keep package Targets relative and contained; Lexeditor must never permit `..`/absolute paths to turn a package rule into an arbitrary-filesystem write.
4. Do not invent PAK/Blueprint editing from the package schema. Those formats need their own evidence and round-trip tests.
5. Do not silently install/replace UE4SS. It is an official package type/runtime dependency with its own compatibility surface.
6. Keep **build**, **local deployment**, **activation**, and **publishing** as separate boundaries:
   - build: clean project-owned package snapshot;
   - local deployment: one Lexeditor-owned unregistered random 10-digit folder, matching Pocketpair's Shift-create convention;
   - activation: Palworld client Mod Management / loader configuration, not silently edited by Lexeditor;
   - publishing: Pocketpair's uploader / Steam registration, not implemented by Lexeditor.
7. Never select or overwrite an existing Workshop folder for a first local deployment. Allocate a fresh folder and persist project-side ownership/digest metadata.
8. Before local deployment, scan visible Workshop packages for duplicate `PackageName`; fail closed because the loader's winner is undefined.
9. On update/removal, trust the currently selected Workshop root rather than a persisted manifest path, reject symlink replacement, and refuse externally modified owned folders.

## References

- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/docs/en/01-General.md
- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/docs/en/02-Package.md
- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/docs/en/03-ModUploader.md
- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/docs/en/04-Tech.md
- https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/MainWindow.xaml.cs
