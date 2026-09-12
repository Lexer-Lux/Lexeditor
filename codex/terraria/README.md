# Terraria / tModLoader

## Supported boundary

Lexeditor's Terraria plugin targets the current **tModLoader 1.4.4 stable** line rather than rewriting vanilla Terraria files directly. The Steam tModLoader application is app `1281930`; vanilla Terraria remains a separate read-only dependency/runtime source.

Current stable documentation identifies tModLoader as the established loader, build system, local mod source workflow, and Workshop publishing path. Mod source projects live under the tModLoader save root's `ModSources/<ModName>/` directory.

## Native source-project shape

A modern source mod uses:

- one source folder whose folder name is the internal mod name;
- `build.txt` for package metadata such as display name, author, version, homepage, visibility/source settings, references and side;
- `<ModName>.csproj` importing `..\tModLoader.targets`;
- exactly one `Terraria.ModLoader.Mod` subclass;
- C# content plus assets/localization beneath the source project;
- tModLoader's own build pipeline to produce the `.tmod` package.

The `..\tModLoader.targets` contract is why Lexeditor-created source projects should default to the real `ModSources` tree instead of inventing an incompatible project layout elsewhere.

The source-folder name is also tModLoader's internal mod name. Lexeditor therefore validates creation and rename **before filesystem mutation** rather than silently sanitizing one generated filename while leaving a different internal name behind. Created names use the exact project folder name for the generated namespace, assembly and source filenames. Lexeditor conservatively accepts ASCII C# identifiers and rejects C# keywords plus tModLoader's reserved `Mod`, `ModLoader` and `tModLoader` names.

## `build.txt` editing boundary

Lexeditor models tModLoader's scalar metadata plus these comma-delimited list properties:

- `modReferences` and `weakReferences`, including `ModName@1.2` version-qualified references;
- `dllReferences`;
- `sortAfter` and `sortBefore`;
- `buildIgnore`.

Structured writes preserve comments/no-equals lines, unknown or future properties, unrelated formatting, BOM state and line endings. Duplicate modeled keys fail closed instead of guessing which occurrence to rewrite. Reference edits also enforce tModLoader's duplicate strong/weak reference rule and the prohibition on duplicating a strong mod reference in `dllReferences`.

Localized `displayName.<culture>` entries remain preservation-only for now.

## Native build handoff

tModLoader exposes a command-line `-build <modFolder>` path that runs its own `ModCompile.BuildModCommandLine` pipeline. Lexeditor uses that path instead of trying to reproduce compilation or packaging itself.

On Windows, the installed `start-tModLoader.bat` ultimately launches `busybox64.exe` with Windows `start`, which detaches the child process. For a synchronous editor build with a meaningful exit code, Lexeditor invokes the same installed bootstrap directly:

`LaunchUtils/busybox64.exe bash ./LaunchUtils/ScriptCaller.sh -build <project> -tmlsavedirectory <save-root>`

`ScriptCaller.sh` then performs tModLoader's normal .NET/bootstrap setup and `exec`s `tModLoader.dll` with those arguments. Passing `-tmlsavedirectory` keeps the build output and local mod state tied to the same save root that owns Lexeditor's `ModSources` project. The expected package is `<save-root>/Mods/<ModName>.tmod`.

The service does not accept an arbitrary executable or command line: the installation root comes from Lexeditor's validated Terraria installation, the project comes from the selected Terraria project, and the remaining arguments are fixed.

A successful synthetic handoff/exit-code test is **not** installed-game acceptance. Final acceptance still requires a real current tModLoader installation to produce and load the package.

## Local package and enabled state

tModLoader stores local packages directly under `<save-root>/Mods` and mirrors its enabled-mod set in `<save-root>/Mods/enabled.json`. Lexeditor reports both the expected local `.tmod` package and whether the selected mod name is present in that native enabled set. Missing `enabled.json` is treated as an empty enabled set, matching tModLoader's loader behavior; malformed or unreadable state is surfaced explicitly instead of guessed.

Lexeditor currently treats `enabled.json` as **read-only**. Native `-build` remains responsible for tModLoader's normal post-build enabling behavior. Lexeditor does not yet expose an independent enable/disable mutation because writing the file behind a running tModLoader process could diverge from tModLoader's cached enabled set.

## Loader / deployment model

- **Loader:** tModLoader itself. Lexeditor does not ship a second Terraria loader.
- **Authoring:** edit a source project under `ModSources`.
- **Build:** invoke tModLoader's native `-build` command through its installed bootstrap.
- **Runtime:** tModLoader loads enabled `.tmod` packages; Workshop remains owned by tModLoader/Steam.
- **State inspection:** report the native local `.tmod` and `Mods/enabled.json` state without rewriting enabled state.
- **Vanilla install:** read-only. Lexeditor must not patch `Terraria.exe` or vanilla content as its normal workflow.

## Research sources

- `tModLoader/tModLoader` stable branch and ExampleMod — authoritative source/project/build conventions (MIT).
- tModLoader stable API docs — current stable version and runtime API surface.
- tModLoader modding documentation/wiki — `ModSources` location and source-project workflow.

## Initial vertical slice

1. detect the Steam tModLoader install;
2. discover/create a valid source mod in `ModSources`;
3. structured `build.txt` inspection/editing with preservation of unknown keys and formatting;
4. Data Map inventory of source code, localization and assets;
5. invoke the supported build path without modifying the installed game;
6. report the resulting local package and tModLoader enabled-state record;
7. verify the resulting local mod is visible/loadable in a real tModLoader install.

Native in-game acceptance is intentionally separate from parser/service/browser checks.
