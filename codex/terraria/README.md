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

New Lexeditor projects also include a rendered `Localization/en-US.hjson` starter rooted at the exact internal mod name so tModLoader can populate generated localization entries in its normal workflow.

## `build.txt` editing boundary

Lexeditor models tModLoader's scalar metadata plus these comma-delimited list properties:

- `modReferences` and `weakReferences`, including `ModName@1.2` version-qualified references;
- `dllReferences`;
- `sortAfter` and `sortBefore`;
- `buildIgnore`.

Structured writes preserve comments/no-equals lines, unknown or future properties, unrelated formatting, BOM state and line endings. Duplicate modeled keys fail closed instead of guessing which occurrence to rewrite. Reference edits also enforce tModLoader's duplicate strong/weak reference rule and the prohibition on duplicating a strong mod reference in `dllReferences`.

Localized `displayName.<culture>` entries remain preservation-only for now.

## Localization editing boundary

tModLoader reads localization from UTF-8 `.hjson` files and derives the culture plus an optional shared key prefix from the path. Lexeditor mirrors the path shapes supported by `LocalizationLoader`, including forms such as:

- `Localization/en-US.hjson`;
- `Localization/en-US_Mods.ExampleMod.hjson`;
- `Localization/en-US/Mods.ExampleMod.hjson`.

For inspection, Lexeditor flattens nested object paths and dotted source keys into the same effective dot-separated keys tModLoader consumes. The special `.$parentVal` component is removed from the effective key to match tModLoader's legacy-conversion behavior.

The structured editor supports **existing single-line string leaves** without reserializing the HJSON document. Editing one supported value preserves comments, object nesting, dotted source keys, whitespace, BOM state, line endings, and every untouched line. Values that would be unsafe as bare HJSON text are emitted as quoted JSON-compatible strings.

Lexeditor can also create a new single-line string key. Creation does not rebuild surrounding objects: it appends one quoted dotted source property at the document root (or immediately inside an explicit root `{ ... }`). Because tModLoader preserves dots in property names while flattening object paths, that dotted property resolves to the requested effective localization key. In prefix-named files such as `en-US_Mods.ExampleMod.hjson`, Lexeditor stores only the key suffix after that file prefix. Existing-value edits and new-key creation are applied in memory and written in one stale-SHA-guarded atomic transaction.

These constructs remain preservation-only/read-only:

- triple-quoted multiline strings;
- arrays and inline complex values;
- booleans, numbers and null values;
- unsupported or ambiguous HJSON expressions;
- files whose path does not identify a known tModLoader culture.

Existing localization-key deletion is not implemented yet. Duplicate effective keys fail closed instead of choosing one occurrence. Structured writes also require the source SHA observed by the editor, so an HJSON file changed by tModLoader, an IDE, or another process must be reloaded before Lexeditor writes it.

This parser is deliberately a preservation-safe editor boundary, **not** a replacement for tModLoader's HJSON parser. Final build/load validation remains authoritative for the complete HJSON grammar.

## C# source editing boundary

Lexeditor exposes project `.cs` files in a raw Source editor so a Terraria mod can be authored without leaving the application. This is deliberately **text editing, not structured C# editing**: Lexeditor does not claim to parse types, methods, hooks, symbols, or tModLoader semantics in this slice.

Source discovery stays inside the selected project and ignores common generated/cache trees such as `obj`, `bin`, `.vs`, `.git`, `out`, and `__pycache__`. Only UTF-8 `.cs` files are opened. Writes are guarded by the SHA observed when the file was loaded, preserve UTF-8 BOM state, preserve an existing all-CRLF newline style even though browser textareas normalize to LF, and replace the file atomically. Path traversal, non-C# paths, NUL content, oversized files, malformed UTF-8, and stale writes fail closed.

The Source editor participates in the same Save/Discard state as metadata and localization. A native Build Mod action is blocked while any source edit is unsaved, and tModLoader's compiler remains authoritative for C# syntax and semantics after saving. Source-file creation/deletion/rename and syntax-aware editing are not implemented yet.

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
- **Metadata:** structured preservation-safe `build.txt` editing.
- **Localization:** structured editing of safe existing single-line HJSON strings plus preservation-safe creation of new dotted string keys; complex constructs remain untouched.
- **C# source:** project-bounded raw UTF-8 text editing with stale-write/BOM/newline preservation; tModLoader owns compilation and semantic validation.
- **Build:** invoke tModLoader's native `-build` command through its installed bootstrap.
- **Runtime:** tModLoader loads enabled `.tmod` packages; Workshop remains owned by tModLoader/Steam.
- **State inspection:** report the native local `.tmod` and `Mods/enabled.json` state without rewriting enabled state.
- **Vanilla install:** read-only. Lexeditor must not patch `Terraria.exe` or vanilla content as its normal workflow.

## Research sources

- `tModLoader/tModLoader` stable branch and ExampleMod — authoritative source/project/build and localization conventions (MIT).
- tModLoader stable API docs — current stable version and runtime API surface.
- tModLoader modding documentation/wiki — `ModSources`, localization and save-root conventions.

## Initial vertical slice

1. detect the Steam tModLoader install;
2. discover/create a valid source mod in `ModSources`;
3. structured `build.txt` inspection/editing with preservation of unknown keys and formatting;
4. structured preservation-safe editing and creation of supported HJSON localization strings;
5. raw project-bounded C# source editing;
6. Data Map inventory of source code, localization and assets;
7. invoke the supported build path without modifying the installed game;
8. report the resulting local package and tModLoader enabled-state record;
9. verify the resulting local mod is visible/loadable in a real tModLoader install.

Native in-game acceptance is intentionally separate from parser/service/browser checks.
