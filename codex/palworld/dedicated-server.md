# Palworld dedicated-server mod deployment

Reviewed 2026-09-09 against Pocketpair's current Palworld Server Guide and `pocketpairjp/PalworldModUploader` technical documentation.

## Supported runtime boundary

Pocketpair's official mod loader supports the **Windows dedicated server**. The dedicated-server Steam application is `2394010`, normally installed as `steamapps/common/PalServer`, with `PalServer.exe` at the root.

Lexeditor does not claim Linux dedicated-server mod-loader support. The normal Palworld server itself supports Linux, but Pocketpair's current mod guide explicitly limits the official server-side mod path to the Windows dedicated server.

## Package source layout

A dedicated server can read package sources from its default local Workshop directory:

```text
<PalServer>/PalServer.exe
<PalServer>/Mods/PalModSettings.ini
<PalServer>/Mods/Workshop/<any folder name>/Info.json
```

The folder name is not the mod identity. `PackageName` in `Info.json` is the loader identity.

Lexeditor deploys its clean package snapshot to one deterministic owned folder:

```text
<PalServer>/Mods/Workshop/Lexeditor-<PackageName>/
```

That target is only created when the clean package contains at least one `InstallRule` with `"IsServer": true`. The package itself remains byte-for-byte equivalent to the clean build input set; Lexeditor ownership manifests stay on the project side and are never inserted into the server package.

## Activation

Unlike the Windows game client, where Pocketpair directs users to Options → Mod Management, dedicated-server operators configure `Mods/PalModSettings.ini` directly.

The relevant official settings are:

```ini
[PalModSettings]
bGlobalEnableMod=true
ActiveModList=PackageName
```

`WorkshopRootDir` is optional for Lexeditor's deployment because the package is placed in the server's documented default `Mods/Workshop` source directory.

Lexeditor activation is an explicit transaction:

1. Require the current clean package to be deployed to the selected server.
2. Require an existing `Mods/PalModSettings.ini`; Pocketpair documents that the server generates this file after it has been launched once.
3. Preserve every unrelated line and add/enable only the minimum loader state needed for the selected `PackageName`.
4. Save an exact-byte copy of the original settings file under the Lexeditor project build state.
5. Record original and post-edit SHA-256 values.
6. Revert only when the current settings SHA-256 still matches Lexeditor's post-edit hash, then restore the original bytes exactly.

If the package was already active before Lexeditor touched the settings file, Lexeditor does not claim ownership and does not create a rollback transaction.

## Server process boundary

Pocketpair applies package/config changes when the dedicated server starts. Lexeditor therefore refuses package deployment, activation, rollback and removal while `PalServer.exe` is running. On Windows the service checks the process list directly. The operator stops the server, makes the change, then restarts it.

A `-NoMods` launch argument still overrides the loader configuration and forcibly disables mods. Lexeditor does not rewrite server launch arguments.

## Version/update behavior

The dedicated server uses the same official loader version semantics documented for Palworld packages:

- if `DebugMode` is false/omitted, a changed package must change its `Version` string before the loader will reinstall it;
- if `DebugMode` is true, the package is reinstalled on every start even when Version is unchanged.

Lexeditor blocks an owned server-package update when its clean payload changed but `Version` stayed the same and `DebugMode` is false.

## Loader installation destinations

For server-compatible `InstallRule` entries (`IsServer: true`), Pocketpair documents these installed destinations after restart:

| Type | Dedicated-server destination |
| --- | --- |
| `UE4SS` | `Mods/NativeMods/UE4SS` |
| `Lua` | `Mods/NativeMods/UE4SS/Mods/{PackageName}` |
| `PalSchema` | `Mods/NativeMods/UE4SS/Mods/PalSchema/mods/{PackageName}` |
| `LogicMods` | `Pal/Content/Paks/LogicMods` |
| `Paks` | `Pal/Content/Paks/~WorkshopMods/{PackageName}` |

The loader creates `Mods/ManagedMods/<PackageName>/InstallManifest.json` automatically after a server restart when it deploys the package. Lexeditor does not synthesize that loader-owned installed state.

## Ownership / failure policy

Lexeditor refuses to overwrite or delete when:

- the target package folder already exists without Lexeditor ownership;
- another server Workshop folder has the same `PackageName`;
- the owned target was changed externally or replaced with a link;
- the project/server root or `PackageName` no longer matches the ownership manifest;
- `PalModSettings.ini` changed after Lexeditor activation;
- the activation recovery copy is missing or has the wrong digest;
- the package remains listed in externally owned server activation state;
- `PalServer.exe` is running.

## Still requiring native acceptance

Synthetic regressions prove filesystem/config preservation and rollback. They do **not** prove that a particular real Palworld server build successfully loads a particular mod. Native acceptance still requires a real Windows `PalServer.exe` installation, restart, and observation of loader-created `Mods/ManagedMods/<PackageName>/InstallManifest.json` / runtime behavior.

## Sources

- Pocketpair Palworld Server Guide — Installing Mods on a Server: `https://docs.palworldgame.com/settings-and-operation/mod/`
- Pocketpair Palworld Server Guide — Deploy dedicated server: `https://docs.palworldgame.com/getting-started/deploy-dedicated-server/`
- Pocketpair `PalworldModUploader/docs/en/04-Tech.md`
