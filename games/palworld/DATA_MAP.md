# Palworld Data Map

Current scope targets **Palworld Windows Steam v0.7+ official mod packages** plus a conservative PalSchema raw-table vertical slice. Installed game data stays read-only.

| Data family | Typical location | Status | Lexeditor boundary |
| --- | --- | --- | --- |
| Official package metadata | `<package>/Info.json` | **Structured + editable** | Parse/validate known fields, preserve unknown keys, stale-hash guard, byte-exact no-op, atomic changed writes + backup. |
| Package install rules | `Info.json -> InstallRule[]` | **Structured + editable** | Official `Lua`, `Paks`, `LogicMods`, `UE4SS`, and `PalSchema` types; client/server flag and target paths. |
| Package dependencies / Workshop tags | `Info.json` | **Structured + editable** | Package-name validation; official tags named while unknown future tags are preserved. |
| PalSchema raw JSON patches | `<PalSchema target>/<mod>/raw/*.json` | **Structured + editable, existing scalar properties** | Mirrors PalSchema's table → row → property patch model. Existing string/bool/int/float values are editable with type preservation, stale hashes, atomic writes and backups. |
| PalSchema raw JSONC patches | `<PalSchema target>/<mod>/raw/*.jsonc` | **Structured + read-only** | Comments are parsed compatibly with PalSchema. Changed writes are intentionally blocked so Lexeditor never destroys comments. |
| PalSchema wildcards / filters | raw row names containing `*`, optional `$Filters` | **Recognized + read-only** | `$Filters` is recognized and validated as an array. Semantic filter editing is not claimed yet. |
| PalSchema row additions/deletions | missing rows / `null` row values | **Recognized + read-only** | Runtime semantics are known, but adding/deleting rows needs schema-backed controls before Lexeditor writes them. |
| PalSchema nested properties | objects/arrays within a row patch | **Readable + read-only** | Preserved on scalar writes. Schema-backed nested editing is future work. |
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

Official `Type=PalSchema` target -> discover direct `<mod>/raw/*.json[c]` -> parse table/row/property patches -> show typed existing scalar properties -> edit `.json` scalar -> preserve unmodeled nested values -> reopen/read back. Discovery is non-recursive because PalSchema's own loader uses a direct directory iterator. JSONC no-op reads are supported, but changed JSONC writes remain blocked to preserve comments.

## Explicitly not claimed yet

- no automatic Workshop activation/deployment;
- no automatic UE4SS or PalSchema runtime installation/update;
- no schema-backed validation against the user's generated PalSchema schemas yet;
- no PalSchema wildcard/filter, row-add/delete, or complex nested-property writer;
- no Unreal `.pak`, `.uasset`, `.uexp`, Blueprint, map, or arbitrary asset parser;
- no real-game or dedicated-server acceptance yet.
