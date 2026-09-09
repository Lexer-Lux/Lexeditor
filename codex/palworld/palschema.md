# PalSchema raw-table mechanics

Reviewed against `Okaetsu/PalSchema` main and release 0.6.7 on 2026-09-09.

## Runtime / version boundary

PalSchema is a UE4SS-based Palworld data-patching runtime. Upstream release 0.6.7 (published 2026-09-04) states that it must be used with Okaetsu's UE4SS build `2281fa31`. Lexeditor does **not** install or replace either runtime; it authors package payloads that the official Palworld loader can install through an `InstallRule` of `Type=PalSchema`.

Pocketpair's official uploader creates PalSchema package targets as `./PalSchema/`, and the official loader installs that target under:

`Mods/NativeMods/UE4SS/Mods/PalSchema/mods`

## Mod tree

PalSchema's normal runtime tree contains one folder per mod beneath its `mods` directory. Loader-specific subfolders include `appearance`, `blueprints`, `buildings`, `enums`, `helpguide`, `items`, `pals`, `raw`, `skins`, `spawns`, and `translations`. These families have different loaders and must not be treated as interchangeable JSON.

## Raw table loader

A raw patch is a direct `.json` or `.jsonc` child of:

`<PalSchema mods root>/<mod>/raw/`

Upstream `ParseJsonFilesInPath` uses `std::filesystem::directory_iterator`; it is not recursive. Lexeditor mirrors that exact discovery boundary.

The root JSON shape is:

```text
DataTable name
  -> row name
    -> property name: patch value
```

The upstream guide demonstrates `DT_PalMonsterParameter -> Kitsunebi -> WorkSuitability_EmitFlame`. PalSchema applies only targeted properties, avoiding whole-asset replacement when separate mods touch different fields.

## Proven row semantics

From `PalRawTableLoader.cpp`:

- a `Rows` key beneath a DataTable is explicitly rejected;
- a row key containing `*` is treated as a wildcard;
- wildcard rows may contain `$Filters`, which is an array whose filters must all match;
- a `null` row deletes that row;
- a missing row is added;
- an existing row gets only its named properties modified;
- an unknown property is logged rather than silently becoming a different field.

Lexeditor reads/recognizes all of these mechanics, but the writable surface is narrower: ordinary scalar edits plus schema-backed scalar-property additions to an **explicit row already present in the patch**. Wildcards, new-row creation, row deletion and nested values remain read-only.

## Generated JSON schemas

PalSchema's own `JsonSchemaGenerator` writes its schemas under:

`Mods/PalSchema/schemas`

In Pocketpair's official loader layout that resolves to:

`<Palworld>/Mods/NativeMods/UE4SS/Mods/PalSchema/schemas`

Lexeditor auto-detects that installed path and also accepts `LEXEDITOR_PALWORLD_PALSCHEMA_SCHEMAS` as an explicit override. The schema tree is **read-only input**; Lexeditor never generates or modifies it.

`GenerateRawSchemas` writes:

- `raw.schema.json` — top-level DataTable catalog;
- `raw/<DataTable>.schema.json` — each row struct's generated property schema;
- `enums.schema.json` — enum definitions referenced from DataTable properties;
- `utility.schema.json` — shared path constraints referenced by object/class properties;
- additional schema files for other PalSchema loader families.

For each DataTable, the per-table file uses `additionalProperties.properties` as the row-property catalog. Generated property types include:

- Unreal integer properties -> JSON Schema `integer`;
- floating-point properties -> `number`;
- bool -> `boolean`;
- FString/FText/FName -> `string`;
- struct -> `object` with nested `properties`;
- arrays/maps -> complex array/`oneOf` shapes;
- enum -> `string` plus `$ref` into `enums.schema.json`;
- object/class paths -> `string` plus `$ref` into `utility.schema.json`.

### Utility object/class path constraints

Upstream's generated `utility.schema.json` defines two path-string references used by raw DataTable schemas:

- `ObjectPathRegex`: `^/Game(?:/[^/]+)*/([A-Za-z0-9_]+)\.\1$`
- `ClassPathRegex`: `^/Game(?:/[^/]+)*/([A-Za-z0-9_]+)\.\1_C$`

The first requires a `/Game/.../Asset.Asset` object path; the second requires `/Game/.../Asset.Asset_C` for a class path.

Lexeditor resolves **only these two named generated utility definitions**. For an object/class path field already present in a writable raw `.json` patch:

- the referenced utility definition must exist in the user's generated `utility.schema.json`;
- the current value must match the generated regex before editing is enabled;
- every replacement value must match that same generated regex at save time;
- missing, malformed or future/unknown utility definitions remain fail-closed.

Object/class path fields remain **non-addable** through the Add Property workflow. The generated regex proves path syntax, but it does not prove that an arbitrary user-entered asset actually exists in the installed game. Adding such a field safely therefore needs a concrete asset-identity source, not just JSON Schema syntax.

### Lexeditor schema policy

When generated schemas are absent, existing scalar JSON values remain editable only with their current JSON type preserved.

When generated schemas are present, they become the write authority:

- integer/number/bool/string types drive semantic controls and server validation;
- resolved enum refs become selects and values outside the generated enum list are rejected;
- resolved existing `ObjectPathRegex` / `ClassPathRegex` fields are regex-validated strings;
- a field missing from the generated DataTable schema becomes read-only;
- a patch value mismatching the generated type or supported utility regex becomes read-only;
- complex object/array/map properties remain read-only;
- unresolved enum, utility or other referenced constraints fail closed rather than degrading to arbitrary strings.

## Schema-backed property addition

Lexeditor can list generated scalar properties that are absent from an **existing explicit patch row**. Adding one is kept in memory as a normal dirty edit until Save, then serialized atomically with any ordinary scalar changes.

The add path deliberately refuses:

- new row names;
- wildcard rows;
- duplicate fields;
- missing schemas;
- complex fields;
- referenced utility/object/class constraints;
- unresolved referenced constraints;
- invalid enum/type values.

This avoids the dangerous PalSchema behavior where a typo in a new row name can create a default-initialized DataTable row, and avoids inventing object/class asset identities from syntactically valid strings.

## JSONC

PalSchema passes `ignore_comments=true` to nlohmann/json only for `.jsonc`. Lexeditor strips comments only for parsing and keeps original bytes untouched on no-op. Changed `.jsonc` writes are blocked because ordinary JSON serialization would destroy comments. `.json` is the writable structured format.

## Preservation and conflict model

Lexeditor writes:

- preserve unrelated tables, rows, fields and nested values;
- require the source SHA-256 seen by the editor;
- create a `.lexeditor.bak` before changed writes;
- write atomically;
- never scan outside current official `Type=PalSchema` package targets;
- never modify PalSchema's generated schema files.

At runtime, PalSchema applies targeted properties rather than replacing a complete source DataTable asset. Lexeditor therefore documents these as semantic field-level runtime patches, while not claiming or imposing a deterministic winner when two runtime patches target the same field.

## Sources

- `Okaetsu/PalSchema` — MIT
- `website/docs/gettingstarted.md`
- `website/docs/guides/rawtables/*`
- `src/Loader/PalRawTableLoader.cpp`
- `src/Loader/WildcardFilter/*`
- `src/Utility/JsonHelpers.cpp`
- `src/Generator/JsonSchema/JsonSchemaGenerator.cpp`
- `assets/schemas/utility.schema.json`
- Pocketpair `PalworldModUploader` package/InstallRule documentation and PalSchema template target.
