# Palworld Data Map

Current scope targets **Palworld Windows Steam v0.7+ official mod packages**, a conservative PalSchema raw-table editor, clean package builds, reversible client-local testing, and an ownership-safe Windows dedicated-server deployment path. Installed game data stays read-only.

| Data family | Typical location | Status | Lexeditor boundary |
| --- | --- | --- | --- |
| Official package metadata | `<package>/Info.json` | **Structured + editable** | Parse/validate known fields, preserve unknown keys, stale-hash guard, byte-exact no-op, atomic changed writes + backup. |
| Package install rules | `Info.json -> InstallRule[]` | **Structured + editable** | Official `Lua`, `Paks`, `LogicMods`, `UE4SS`, and `PalSchema` types; client/server flag and target paths. |
| Package dependencies / Workshop tags | `Info.json` | **Structured + editable** | Package-name validation; official tags named while unknown future tags are preserved. |
| Clean official-package snapshot | `<project>/build/official-package/**` | **Build + reversible** | Copies only `Info.json`, referenced thumbnail and declared InstallRule targets; excludes Lexeditor recovery/temp artifacts, rejects missing targets/symlinks, ownership/digest tracks the output, and refuses external modifications. |
| Local test Workshop deployment | `steamapps/workshop/content/1623730/<random-10-digit>/` | **Deploy + reversible** | Mirrors Pocketpair Mod Uploader's Shift-created unregistered local test package shape. Requires a current clean build, rejects duplicate `PackageName`, owns only its fresh 10-digit folder, detects external changes/root tampering/symlink replacement, and removes only the unchanged owned folder. |
| Steam Workshop subscribed/published items | `steamapps/workshop/content/1623730/<Steam-item-id>/` | **Read-only / not managed** | Lexeditor never chooses an existing subscribed item as its local test folder, never overwrites another item, and does not create/upload Steam Workshop registrations. |
| Client loader activation config | `<Palworld>/Mods/PalModSettings.ini` | **Read-only loader state** | Lexeditor reads global enable state, `WorkshopRootDir`, and repeated `ActiveModList` entries so Build can report whether the current `PackageName` is active. Client activation remains owned by Palworld Options → Mod Management; Lexeditor never writes this file. |
| Windows dedicated-server package source | `<PalServer>/Mods/Workshop/Lexeditor-<PackageName>/**` | **Deploy + reversible** | Requires a current clean build and at least one `InstallRule` with `IsServer: true`. Project-side digest/ownership state protects the deterministic server Workshop folder; collisions, links, missing owned state and external changes fail closed. |
| Dedicated-server activation config | `<PalServer>/Mods/PalModSettings.ini` | **Explicit reversible edit** | Pocketpair requires direct configuration on dedicated servers. Lexeditor preserves unrelated lines, records the exact original bytes + pre/post SHA-256, and restores them only while the post-edit file remains unchanged. An already-active external config is never claimed. |
| Dedicated-server process state | `PalServer.exe` | **Safety gate** | On Windows, package/config mutations are blocked while the server process is running. Stop the server before changes and restart it afterward; `-NoMods` can still override the config externally. |
| PalSchema generated schemas | `<Palworld>/Mods/NativeMods/UE4SS/Mods/PalSchema/schemas/**` | **Read-only validation source** | Auto-detected when installed; optional `LEXEDITOR_PALWORLD_PALSCHEMA_SCHEMAS` override. Raw DataTable field types, enum definitions, and supported utility path constraints become write authority; Lexeditor never rewrites generated schemas. |
| PalSchema raw JSON patches | `<PalSchema target>/<mod>/raw/*.json` | **Structured + editable** | Existing scalar properties are editable. With generated schemas, resolved scalar properties can also be added to an explicit row already present in the patch. Stale hashes, atomic writes and backups apply. |
| PalSchema raw JSONC patches | `<PalSchema target>/<mod>/raw/*.jsonc` | **Structured + read-only** | Comments are parsed compatibly with PalSchema. Changed writes are intentionally blocked so Lexeditor never destroys comments. |
| PalSchema schema enums | `schemas/enums.schema.json` | **Structured validation** | Resolved enum refs become semantic selects and reject values outside the generated enum list. Missing/unresolved enum refs fail closed. |
| PalSchema object/class path refs | `schemas/utility.schema.json -> ObjectPathRegex / ClassPathRegex` | **Structured validation for existing fields** | Existing string fields using these two generated utility refs are editable only when the utility definition resolves; new values must match the generated regex. Unknown/missing utility refs fail closed. These refs remain non-addable because the schema proves path syntax, not asset existence. |
| PalSchema wildcards / filters | raw row names containing `*`, optional `$Filters` | **Recognized + read-only** | `$Filters` is recognized and validated as an array. Add-property and ordinary semantic editors do not operate on wildcard rows. |
| PalSchema new-row creation / row deletion | missing rows / `null` row values | **Recognized + read-only** | Runtime semantics are known, but Lexeditor will not create or delete rows until row identity/existing-game-data evidence is stronger. |
| PalSchema nested properties | objects/arrays within a row patch | **Readable + read-only** | Preserved on scalar writes. Generated struct/array/map schemas are recognized as complex and remain read-only. |
| Other PalSchema loader families | `appearance/`, `blueprints/`, `buildings/`, `enums/`, `helpguide/`, `items/`, `pals/`, `skins/`, `spawns/`, `translations/` | **Recognized, unsupported** | Do not generalize the raw-table writer to loader families with different semantics. |
| PAK resource replacements | `<package>/Paks/**/*.pak` | **Recognized, unsupported internally** | Package/build/deploy support only; no claim of PAK asset parsing yet. |
| UE4SS Lua mods | package targets using `Type=Lua` | **Recognized, unsupported internally** | Loader/package/build/deploy shape recognized; no generic Lua runtime editor. |
| UE4SS core payload | package targets using `Type=UE4SS` | **Recognized, unsupported internally** | Lexeditor does not bundle or silently replace UE4SS. |
| LogicMods | package targets using `Type=LogicMods` | **Recognized, unsupported internally** | Unreal Blueprint/asset editing is not part of this slice. |
| Installed game/server PAKs/assets | `<Palworld or PalServer>/Pal/Content/Paks/**` | **Loader-owned / read-only** | Never rewritten directly as the normal project save path. The official loader performs installation from package sources. |

## Proven vertical slices

### Official package metadata

`Info.json`: detect package -> decode -> validate -> edit -> serialize -> reopen. Unknown keys survive, unsafe targets fail closed, untouched saves stay byte-exact, changed writes are stale-guarded/atomic/backed up.

### PalSchema raw DataTable patches

Official `Type=PalSchema` target -> discover direct `<mod>/raw/*.json[c]` -> parse table/row/property patches -> optionally load the user's generated DataTable/enum/utility schemas -> show semantic scalar controls -> edit existing scalar -> validate resolved enum and object/class path refs -> add a generated-schema scalar to an already-targeted explicit row -> serialize atomically -> reopen/read back. Unmodeled/nested values survive unchanged. Discovery stays non-recursive because PalSchema's own loader uses a direct directory iterator. JSONC no-op reads are supported but changed JSONC writes remain blocked to preserve comments.

### Clean official-package build

Validate package + known PalSchema raw payloads -> enumerate only official package inputs -> reject missing targets/symlinks -> exclude `.lexeditor.bak`/temporary artifacts -> build atomically to an owned snapshot -> hash/track every output file -> refuse overwrite/revert after external modification -> revert only the unchanged Lexeditor-owned snapshot.

### Pocketpair-style local client test deployment

Require a current clean build -> resolve/verify the Steam Workshop content root -> reject any existing package with the same `PackageName` -> allocate a fresh random 10-digit folder (matching Pocketpair's Shift-create local-test convention) -> atomically copy the clean build -> persist project-side ownership/digest metadata -> refuse update/removal after external modification, root mismatch, missing owned folder or symlink replacement -> remove only the unchanged owned local folder. This proves reversible filesystem deployment, **not** that a real installed Palworld build has loaded the mod yet.

### Windows dedicated-server deployment + activation

Require a current clean build with `IsServer: true` -> locate `PalServer.exe` (explicit `LEXEDITOR_PALWORLD_SERVER_ROOT` or sibling Steam `PalServer`) -> require the server process to be stopped -> copy the clean package atomically into the documented default `Mods/Workshop` source tree -> enforce official Version/DebugMode refresh semantics -> optionally enable the package by transactionally editing `Mods/PalModSettings.ini` -> preserve exact original bytes for stale-guarded rollback -> require server restart for the official loader to deploy files. Unit regressions prove source/config preservation, but real loader acceptance still requires an installed Windows server.

## Explicitly not claimed yet

- no automatic **client** activation or client `PalModSettings.ini` edits;
- no Steam Workshop publishing/registration through Lexeditor;
- no overwrite/update of subscribed Workshop item folders;
- no automatic UE4SS or PalSchema runtime installation/update;
- no PalSchema schema generation inside Lexeditor; generated runtime schemas are consumed read-only;
- no wildcard/filter writer;
- no new-row creation, row deletion, or complex nested-property writer;
- no add-from-scratch object/class path fields without concrete asset-identity evidence;
- no arbitrary/future utility `$ref` support beyond `ObjectPathRegex` and `ClassPathRegex`;
- no Unreal `.pak`, `.uasset`, `.uexp`, Blueprint, map, or arbitrary asset parser;
- no real installed-game or real dedicated-server runtime acceptance yet.
