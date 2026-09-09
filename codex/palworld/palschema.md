# PalSchema raw-table mechanics

Reviewed against `Okaetsu/PalSchema` main and release 0.6.7 on 2026-09-09.

## Runtime / version boundary

PalSchema is a UE4SS-based Palworld data-patching runtime. Upstream release 0.6.7 (published 2026-09-04) states that it must be used with Okaetsu's UE4SS build `2281fa31`. Lexeditor does **not** install or replace either runtime in this slice; it authors package payloads that the official Palworld loader can install through an `InstallRule` of `Type=PalSchema`.

Pocketpair's official uploader creates PalSchema package targets as `./PalSchema/`, and the official loader installs that target under:

`Mods/NativeMods/UE4SS/Mods/PalSchema/mods`

## Mod tree

PalSchema's normal runtime tree contains one folder per mod beneath its `mods` directory. Loader-specific subfolders include:

- `appearance`
- `blueprints`
- `buildings`
- `enums`
- `helpguide`
- `items`
- `pals`
- `raw`
- `skins`
- `spawns`
- `translations`

These families have different loaders and must not be treated as interchangeable JSON.

## Raw table loader

The `raw` loader is the first Lexeditor-integrated family because its semantics are unusually narrow and conflict-resistant.

A raw patch is a direct `.json` or `.jsonc` child of:

`<PalSchema mods root>/<mod>/raw/`

Upstream `ParseJsonFilesInPath` uses `std::filesystem::directory_iterator`; it is not recursive. Lexeditor mirrors that exact discovery boundary.

The root JSON shape is:

```text
DataTable name
  -> row name
    -> property name: patch value
```

For example, the upstream guide edits the `Kitsunebi` row of `DT_PalMonsterParameter` by specifying only `WorkSuitability_EmitFlame`. PalSchema applies only targeted properties, which means separate mods can avoid whole-asset replacement conflicts when they modify different fields.

## Proven row semantics

From `PalRawTableLoader.cpp`:

- a `Rows` key beneath a DataTable is explicitly rejected; users copying FModel output must put row entries directly beneath the table;
- a row key containing `*` is treated as a wildcard;
- wildcard rows may contain `$Filters`;
- `$Filters` is an array and every filter must match;
- a `null` row deletes that row;
- a missing row is added;
- an existing row gets only its named properties modified;
- an unknown property is logged rather than silently becoming a different field.

Lexeditor currently **reads/recognizes** the wildcard, filter, add/delete, and nested-value mechanics but writes only existing scalar properties. That keeps the first writer smaller than PalSchema's schema surface.

## JSONC

PalSchema passes `ignore_comments=true` to nlohmann/json only for `.jsonc`. Lexeditor strips comments only for parsing and keeps the original bytes untouched on no-op. Changed `.jsonc` writes are blocked because ordinary JSON serialization would destroy comments. `.json` files are the structured writable format for this slice.

## Preservation and conflict model

Lexeditor scalar writes:

- preserve existing JSON scalar type;
- preserve all unrelated tables, rows, fields and nested values;
- require the source SHA-256 seen by the editor;
- create a `.lexeditor.bak` copy before changed writes;
- write atomically;
- never scan outside current official `Type=PalSchema` package targets.

At runtime, PalSchema applies targeted properties rather than replacing the complete source DataTable asset. Lexeditor therefore documents PalSchema raw patches as semantic field-level runtime patches, while not claiming a deterministic result when two patches target the same field.

## Sources

- `Okaetsu/PalSchema` — MIT
- `website/docs/gettingstarted.md`
- `website/docs/guides/rawtables/*`
- `src/Loader/PalRawTableLoader.cpp`
- `src/Loader/WildcardFilter/*`
- `src/Utility/JsonHelpers.cpp`
- Pocketpair `PalworldModUploader` package/InstallRule documentation and PalSchema template target.
