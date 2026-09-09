# Palworld Data Map

Current scope targets **Palworld Windows Steam v0.7+ official mod packages** plus a conservative PalSchema raw-table editor. Installed game data stays read-only.

| Data family | Typical location | Status | Lexeditor boundary |
| --- | --- | --- | --- |
| Official package metadata | `<package>/Info.json` | **Structured + editable** | Parse/validate known fields, preserve unknown keys, stale-hash guard, byte-exact no-op, atomic changed writes + backup. |
| Package install rules | `Info.json -> InstallRule[]` | **Structured + editable** | Official `Lua`, `Paks`, `LogicMods`, `UE4SS`, and `PalSchema` types; client/server flag and target paths. |
| Package dependencies / Workshop tags | `Info.json` | **Structured + editable** | Package-name validation; official tags named while unknown future tags are preserved. |
| PalSchema generated schemas | `<Palworld>/Mods/NativeMods/UE4SS/Mods/PalSchema/schemas/**` | **Read-only validation source** | Auto-detected when installed; optional `LEXEDITOR_PALWORLD_PALSCHEMA_SCHEMAS` override. Raw DataTable field types and enum definitions become write authority; Lexeditor never rewrites generated schemas. |
| PalSchema raw JSON patches | `<PalSchema target>/<mod>/raw/*.json` | **Structured + editable** | Existing scalar properties are editable. With generated schemas, resolved scalar properties can also be added to an explicit row already present in the patch. Stale hashes, atomic writes and backups apply. |
| PalSchema raw JSONC patches | `<PalSchema target>/<mod>/raw/*.jsonc` | **Structured + read-only** | Comments are parsed compatibly with PalSchema. Changed writes are intentionally blocked so Lexeditor never destroys comments. |
| PalSchema schema enums | `schemas/enums.schema.json` | **Structured validation** | Resolved enum refs become semantic selects and reject values outside the generated enum list. Missing/unresolved enum refs fail closed. |
| PalSchema referenced object/class constraints | generated `$ref` values outside enums | **Recognized + read-only** | Lexeditor does not broaden a referenced constraint into an arbitrary string; unresolved refs are disabled. |
| PalSchema wildcards / filters | raw row names containing `*`, optional `$Filters` | **Recognized + read-only** | `$Filters` is recognized and validated as an array. Add-property and ordinary semantic editors do not operate on wildcard rows. |
| PalSchema new-row creation / row deletion | missing rows / `null` row values | **Recognized + read-only** | Runtime semantics are known, but Lexeditor will not create or delete rows until row identity/existing-game-data evidence is stronger. |
| PalSchema nested properties | objects/arrays within a row patch | **Readable + read-only** | Preserved on scalar writes. Generated struct/array/map schemas are recognized as complex and remain read-only. |
| Other PalSchema loader families | `appearance/`, `blueprints/`, `buildings/`, `enums/`, `helpguide/`, `items/`, `pals/`, `skins/`, `spawns/`, `translations/` | **Recognized, unsupported** | Do not generalize the raw-table writer to loader families with different semantics. |
| PAK resource replacements | `<package>/Paks/**/*.pak` | **Recognized, unsupported** | Package/inventory support only; no claim of PAK asset parsing yet. |
| UE4SS Lua mods | package targets using `Type=Lua` | **Recognized, unsupported** | Loader/package shape recognized; no generic Lua runtime editor. |
| UE4SS core payload | package targets using `Type=UE4SS` | **Recognized, unsupported** | Lexeditor does not bundle or silently replace UE4SS. |
| LogicMods | package targets using `Type=LogicMods` | **Recognized, unsupported** | Unreal Blueprint/asset editing is not part of this slice. |
| Loader activation config | `<Palworld>/Mods/PalModSettings.ini` | **Known runtime config, not project data** | Official loader owns enable state. Editing/activation remains deferred until reversible deployment is implemented. |
| Installed game PAKs/assets | `<Palworld>/Pal/Content/Paks/**` | **Read-only / not yet mapped** | Never rewritten as the normal project save path. |
| Dedicated-server package variants | `InstallRule[].IsServer` | **Metadata editable; native acceptance pending** | Rules can be represented, but dedicated-server deployment has not been accepted against a real server install. |

## Proven vertical slices

### Official package metadata

`Info.json`: detect package -> decode -> validate -> edit -> serialize -> reopen. Unknown keys survive, unsafe targets fail closed, untouched saves stay byte-exact, changed writes are stale-guarded/atomic/backed up.

### PalSchema raw DataTable patches

Official `Type=PalSchema` target -> discover direct `<mod>/raw/*.json[c]` -> parse table/row/property patches -> optionally load the user's generated DataTable/enum schemas -> show semantic scalar controls -> edit existing scalar -> add a generated-schema scalar to an already-targeted explicit row -> serialize atomically -> reopen/read back. Unmodeled/nested values survive unchanged. Discovery stays non-recursive because PalSchema's own loader uses a direct directory iterator. JSONC no-op reads are supported but changed JSONC writes remain blocked to preserve comments.

## Explicitly not claimed yet

- no automatic Workshop activation/deployment;
- no automatic UE4SS or PalSchema runtime installation/update;
- no PalSchema schema generation inside Lexeditor; generated runtime schemas are consumed read-only;
- no wildcard/filter writer;
- no new-row creation, row deletion, or complex nested-property writer;
- no resolution/editor for utility/object/class `$ref` constraints yet;
- no Unreal `.pak`, `.uasset`, `.uexp`, Blueprint, map, or arbitrary asset parser;
- no real-game or dedicated-server acceptance yet.
