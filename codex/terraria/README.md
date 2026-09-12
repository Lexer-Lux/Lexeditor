# Terraria / tModLoader

## Supported boundary

Lexeditor's Terraria plugin targets the current **tModLoader 1.4.4 stable** line rather than rewriting vanilla Terraria files directly. The Steam tModLoader application is app `1281930`; vanilla Terraria remains a separate read-only dependency/runtime source.

Current stable tModLoader is the loader, build system, source-project workflow, local package format and Workshop path. Lexeditor therefore authors native tModLoader projects and hands compilation/loading back to tModLoader instead of inventing a parallel Terraria mod format.

## Native source-project shape

A modern source mod uses:

- one source folder under `ModSources/<ModName>/`, whose folder name is the internal mod/package name;
- `build.txt` for package metadata, dependencies and build behavior;
- `<ModName>.csproj` importing `..\tModLoader.targets`;
- a `Terraria.ModLoader.Mod` subclass plus C# content types;
- HJSON localization and packaged resources;
- tModLoader's own build pipeline to produce `<save-root>/Mods/<ModName>.tmod`.

Lexeditor-created projects use that native layout. Project names are validated **before filesystem mutation** as conservative ASCII C# identifiers and reject C# keywords plus tModLoader's reserved `Mod`, `ModLoader` and `tModLoader` names. Creation renders matching namespace/assembly/source names and a `Localization/en-US.hjson` starter.

Renaming the project folder changes the tModLoader internal/package name. Lexeditor deliberately does **not** attempt a global semantic C# namespace/type refactor when a project is renamed; source identifiers remain ordinary author-controlled C#.

## `build.txt` editing

Lexeditor models tModLoader's scalar metadata plus these comma-delimited list properties:

- `modReferences` and `weakReferences`, including `ModName@1.2` version-qualified references;
- `dllReferences`;
- `sortAfter` and `sortBefore`;
- `buildIgnore`.

Structured writes preserve comments/no-equals lines, unknown or future properties, unrelated formatting, BOM state and line endings. Duplicate modeled keys fail closed. Reference edits enforce tModLoader's duplicate strong/weak-reference rule and the prohibition on duplicating a strong mod reference in `dllReferences`.

Localized `displayName.<culture>` lines in `build.txt` remain preservation-only.

## Localization editing

tModLoader reads UTF-8 `.hjson` localization files and derives culture plus an optional shared key prefix from the file path. Lexeditor mirrors supported forms such as:

- `Localization/en-US.hjson`;
- `Localization/en-US_Mods.ExampleMod.hjson`;
- `Localization/en-US/Mods.ExampleMod.hjson`.

For inspection, nested object paths and dotted source keys are flattened into the effective dot-separated keys used by tModLoader. The special `.$parentVal` component is removed from the effective key to mirror tModLoader's legacy-conversion behavior.

The structured editor supports existing **single-line string leaves** without reserializing the HJSON document. Edits preserve comments, nesting, dotted source keys, whitespace, BOM state, line endings and every untouched line. Unsafe bare values are emitted as quoted JSON-compatible strings.

Lexeditor can also create new single-line string keys by appending a quoted dotted property at the document root (or inside an explicit root object). Prefix-named files store only the suffix after the file prefix. Existing editable single-line leaves can also be deleted by removing their complete source line. Updates, creations and deletions are applied together under one stale-SHA-guarded transaction, and contradictory operations on the same key are rejected.

These constructs remain preservation-only/read-only:

- triple-quoted multiline strings;
- arrays and inline complex values;
- booleans, numbers and null values;
- unsupported or ambiguous HJSON expressions;
- files whose path does not identify a known tModLoader culture.

Duplicate effective keys fail closed. Direct API paths are project-bounded and reject hidden/generated trees such as `.git`, `.vs`, `obj`, `bin`, caches and other dot-prefixed directories.

This editor is intentionally a preservation-safe subset, **not** a replacement for tModLoader's full HJSON parser. Native build/load remains authoritative.

## C# source editing

The Source tab exposes project `.cs` files as raw UTF-8 text. It is deliberately **not a syntax-/semantic-aware C# model**: Lexeditor does not rewrite symbols, hooks, types or namespaces automatically.

Source discovery and direct source API calls remain inside the selected project and reject generated/hidden trees. Reads reject malformed UTF-8, NUL content and oversized files. Saves use the SHA observed when the file was loaded, preserve UTF-8 BOM state, preserve an existing all-CRLF newline style despite browser textarea LF normalization, and replace atomically.

Lexeditor can:

- create new project-relative `.cs` files without overwrite;
- edit them through shared Save/Discard state;
- rename/move a source file without overwrite and under a stale-SHA guard;
- delete a source file under the same stale-SHA guard.

Native Build Mod is blocked while metadata, localization or source text has unsaved changes.

## Content scaffolds

The Content tab provides deliberately conservative high-level starting points against the current stable tModLoader APIs:

- **ModItem** — creates `Content/Items/<Name>.cs`, standard en-US `DisplayName` and optional `Tooltip` localization, and a visible replaceable 16×16 PNG. Generated C# sets only `Item.width` and `Item.height`; damage, damage class, use behavior, rarity, value, recipes, sounds and other gameplay decisions are left to the author.
- **ModSystem** — creates an empty `Common/Systems/<Name>.cs` class deriving from `ModSystem`.
- **ModPlayer** — creates an empty `Common/Players/<Name>.cs` class deriving from `ModPlayer`.

Scaffolds never overwrite existing source/assets. The generated files immediately become ordinary Source/Localization/Assets entries for further editing.

Gameplay-heavy structured generators such as ModNPC/ModProjectile/ModTile are intentionally not claimed yet; raw C# remains available for them.

## Asset management

tModLoader packages non-ignored project resources and has runtime readers/converters for common source asset formats. Lexeditor inventories and manages these known formats anywhere inside the project:

- PNG;
- XNB;
- RAWIMG;
- FXC;
- WAV;
- MP3;
- OGG.

Asset import is exclusive-create; replacement is SHA-guarded and atomic; rename/move is SHA-guarded, refuses overwrite and preserves the file extension; delete is also SHA-guarded. Hidden/generated paths are rejected by the API itself. Lexeditor applies a 16 MiB management cap and lightweight signature validation for preview-oriented PNG/WAV/OGG files.

PNG receives browser image preview plus dimensions. WAV/MP3/OGG receive browser audio preview. XNB/RAWIMG/FXC remain inspect/replace assets; Lexeditor does not claim semantic decoding/editing of compiled formats.

## Native build handoff and diagnostics

tModLoader exposes command-line `-build <modFolder>` through its own build pipeline. Lexeditor invokes that native path instead of reproducing compilation or `.tmod` packaging.

On Windows, Lexeditor invokes the installed synchronous bootstrap directly:

`LaunchUtils/busybox64.exe bash ./LaunchUtils/ScriptCaller.sh -build <project> -tmlsavedirectory <save-root>`

The installation root comes from Lexeditor's validated Terraria installation, the project comes from the selected Terraria project, and command arguments are fixed rather than caller-supplied.

The build service provides:

- concurrency protection;
- a bounded build timeout;
- stdout/stderr and tModLoader native-log tails;
- expected `.tmod` artifact verification;
- parsed standard C#/MSBuild errors and warnings with file, line/column, code and message;
- project-relative diagnostics that can jump directly to the reported Source line.

Raw logs remain available because tModLoader can emit useful non-compiler diagnostics that do not match the structured C# parser.

Synthetic command/diagnostic tests do **not** count as installed-game acceptance.

## Local package and enabled state

tModLoader stores local packages under `<save-root>/Mods` and mirrors its enabled-mod set in `<save-root>/Mods/enabled.json`. Lexeditor reports the expected local `.tmod` and whether the selected mod name is present in that native enabled set.

Missing `enabled.json` is treated as an empty enabled set, matching tModLoader behavior; malformed/unreadable state is surfaced rather than guessed. Lexeditor keeps `enabled.json` **read-only** because writing behind a running tModLoader process could diverge from tModLoader's cached state. Native `-build` remains responsible for normal post-build enabling.

## Loader / deployment model

- **Loader/runtime:** tModLoader itself; Lexeditor ships no second Terraria loader.
- **Authoring:** native `ModSources` project.
- **Metadata:** preservation-safe structured `build.txt` editing.
- **Localization:** supported single-line HJSON edit/create/delete subset, with complex grammar untouched.
- **C# source:** project-bounded raw text create/edit/rename/delete.
- **Content:** conservative ModItem/ModSystem/ModPlayer scaffolds plus raw Source for everything else.
- **Assets:** known-format import/replace/rename/delete with preview where practical.
- **Build:** native tModLoader `-build` with structured C# diagnostics plus raw logs.
- **Runtime state:** report local package and native enabled state without rewriting it.
- **Vanilla Terraria install:** read-only.

## Research basis

- `tModLoader/tModLoader` stable branch and ExampleMod — source/project/build/localization/content conventions (MIT).
- tModLoader `LocalizationLoader` — culture/prefix inference and effective localization-key behavior.
- tModLoader `ModItem`, `ModSystem` and `ModPlayer` APIs / ExampleMod — scaffold boundaries.
- tModLoader `AssetInitializer` and `ContentConverters` — runtime asset readers/conversion behavior.
- tModLoader `ModCompile` — resource packaging and native command-line build behavior.
- tModLoader stable API docs/wiki — `ModSources`, localization and save-root conventions.

## Acceptance boundary

Automated parser/service/editor tests and synthetic native-build handoff tests are not installed-game acceptance. Final acceptance requires a real current **Windows tModLoader 1.4.4 stable** installation to:

1. build a Lexeditor-created source project through the actual installed bootstrap;
2. produce/expose the local `.tmod` in tModLoader;
3. load representative Lexeditor-authored metadata, localization, C# and asset/content-scaffold changes in game.

That installed-runtime acceptance is intentionally the remaining hard boundary.