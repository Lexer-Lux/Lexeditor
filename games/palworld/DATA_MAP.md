# Palworld Data Map

Initial scope targets the **official Palworld v0.7+ mod-package boundary**. Installed game data stays read-only. Coverage labels are intentionally conservative.

| Data family | Typical location | Status | Lexeditor boundary |
| --- | --- | --- | --- |
| Official package metadata | `<package>/Info.json` | **Structured + editable** | Parse/validate known fields, preserve unknown keys, stale-hash guard, byte-exact no-op, atomic changed writes + backup. |
| Package install rules | `Info.json -> InstallRule[]` | **Structured + editable** | Official `Lua`, `Paks`, `LogicMods`, `UE4SS`, and `PalSchema` types; client/server flag and target paths. |
| Package dependencies / Workshop tags | `Info.json` | **Structured + editable** | Package-name validation; official tags named while unknown future tags are preserved. |
| PAK resource replacements | `<package>/Paks/**/*.pak` | **Recognized, unsupported** | Package/inventory support first; no claim of PAK asset parsing yet. |
| UE4SS Lua mods | `<package>/Scripts/**` (via Lua install rules) | **Recognized, unsupported** | Do not invent a Lua/runtime model before a representative existing mod is researched. |
| UE4SS core payload | package targets using `Type=UE4SS` | **Recognized, unsupported** | Loader-owned runtime payload; Lexeditor will not bundle or silently replace UE4SS. |
| LogicMods | `<package>/LogicMods/**` | **Recognized, unsupported** | Unreal payload parsing/editing not implemented in the first slice. |
| PalSchema packages | `<package>/PalSchema/**` | **Recognized, unsupported** | Dependency/package shape recognized; PalSchema data-table editing is future research. |
| Loader activation config | `<Palworld>/Mods/PalModSettings.ini` | **Known runtime config, not project data** | Official loader owns enable state. Editing/activation is deferred until reversible deployment is implemented. |
| Installed game PAKs/assets | `<Palworld>/Pal/Content/Paks/**` | **Read-only / not yet mapped** | Never rewritten as the normal project save path. |
| Dedicated-server package variants | `InstallRule[].IsServer` | **Metadata editable; native acceptance pending** | Rules can be represented, but dedicated-server deployment has not yet been accepted against a real server install. |

## First vertical slice

`Info.json`: detect package -> decode -> validate -> edit -> serialize -> reopen. The package write path preserves unknown JSON keys, rejects unsafe target traversal, skips untouched writes byte-for-byte, makes a backup before changed writes, and refuses stale-source saves.

## Explicitly not claimed yet

- no Unreal `.pak`, `.uasset`, `.uexp`, Blueprint, DataTable, or map parser;
- no automatic UE4SS install/update;
- no Steam Workshop publishing through Lexeditor;
- no activation/deactivation edits to `PalModSettings.ini`;
- no real-game or dedicated-server acceptance yet.
