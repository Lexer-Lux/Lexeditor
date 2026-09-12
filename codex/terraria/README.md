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

## `build.txt` editing boundary

Lexeditor models tModLoader's scalar metadata plus these comma-delimited list properties:

- `modReferences` and `weakReferences`, including `ModName@1.2` version-qualified references;
- `dllReferences`;
- `sortAfter` and `sortBefore`;
- `buildIgnore`.

Structured writes preserve comments/no-equals lines, unknown or future properties, unrelated formatting, BOM state and line endings. Duplicate modeled keys fail closed instead of guessing which occurrence to rewrite. Reference edits also enforce tModLoader's duplicate strong/weak reference rule and the prohibition on duplicating a strong mod reference in `dllReferences`.

Localized `displayName.<culture>` entries remain preservation-only for now.

## Loader / deployment model

- **Loader:** tModLoader itself. Lexeditor does not ship a second Terraria loader.
- **Authoring:** edit a source project under `ModSources`.
- **Build:** use tModLoader's supported mod build pipeline / generated MSBuild targets.
- **Runtime:** tModLoader loads enabled `.tmod` packages; Workshop remains owned by tModLoader/Steam.
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
6. verify the resulting local mod is visible/loadable in a real tModLoader install.

Native in-game acceptance is intentionally separate from parser/service/browser checks.
