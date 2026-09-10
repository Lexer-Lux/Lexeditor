# FINAL FANTASY X/X-2 HD Remaster — Steam collection

## Product boundary

- Steam app ID: `359870`.
- Common install directory: `FINAL FANTASY FFX&FFX-2 HD Remaster`.
- Collection launcher: `FFX&X-2_LAUNCHER.exe`.
- Game executables: `FFX.exe` and `FFX-2.exe`.
- Primary archives: `data/FFX_Data.vbf` and `data/FFX2_Data.vbf`.

Lexeditor treats both games as one plugin because Steam ships them as one collection and Fahrenheit supports both archives from one framework installation. Play intentionally bypasses the Square Enix collection launcher and targets each game through Fahrenheit Stage 0 directly.

## VBF read contract

The integrated VBF reader is read-only. `michivi/vbf-fs` establishes the format used here:

1. ASCII signature `SRYK`.
2. 32-bit little-endian header length.
3. 64-bit little-endian file count.
4. 16-byte MD5 path hash per file.
5. 32-byte file-entry records.
6. Length-prefixed NUL-terminated name table.
7. 16-bit block descriptors for 64 KiB logical blocks.
8. zlib-compressed or passthrough payload blocks.
9. Final 16-byte MD5 of the complete header.

Lexeditor validates signature, header hash, per-path MD5, table boundaries, data offsets, path safety and decompressed lengths before exposing an entry.

Real archive names may omit the game-facing virtual archive root. Lexeditor resolves both raw `ffx_ps2/...` and virtual `FFX_Data/ffx_ps2/...` spellings, but always stages FFX replacements beneath `efl/x/FFX_Data/...`; FFX-2 equivalently uses `efl/x2/FFX2_Data/...`.

## FFX fixed-record container

`FFXDataParser` is a research cross-check for the common FFX fixed-record container. Lexeditor independently implements only these container facts:

- minimum index: `u16` at `0x08`;
- maximum index: `u16` at `0x0A`;
- record size: `u16` at `0x0C`;
- total fixed-record bytes: `u16` at `0x0E`;
- records begin at `0x14`;
- bytes after the record region remain opaque and are preserved exactly.

Inconsistent ranges, zero record sizes, mismatched byte counts and truncated regions fail closed.

## Structured FFX tables

### `takara.bin` — treasure rewards

Path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin`

Writable fields only:

- `+0x00`: reward kind (`u8`);
- `+0x01`: quantity (`u8`);
- `+0x02..+0x03`: type ID (`u16`).

Known kinds are gil, item/command, gear and key item. Unknown kinds remain representable. All other bytes are preserved.

### `item_rate.bin` — item/command prices

Path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_rate.bin`

Each record is one little-endian `u32` gil price. Ordinal zero maps to command/item ID `0x2000`. Only selected four-byte prices are written.

### `arms_rate.bin` — auto-ability prices

Path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_rate.bin`

Same proved four-byte price-table shape; ordinal zero maps to auto-ability ID `0x8000`.

### `a_ability.bin` — auto-ability elemental masks

English/US path:

`FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/a_ability.bin`

This editor is deliberately narrow. Two independent sources establish the fields Lexeditor exposes:

- `Karifean/FFXDataParser` identifies `a_ability.bin`, record length `0x6C`, and maps bytes `+0x11..+0x15` as elemental Strike, Absorb, Immune, Resist and Weak masks. Its default localization is `us`, with localization root `ffx_ps2/ffx/master/new_uspc/`.
- Fahrenheit independently asserts `sizeof(FFX.AutoAbility) == 0x6C` for `a_ability.bin`. Its sequential `AutoAbility` structure places SOS at `+0x10`, followed by the same five one-byte elemental fields; `ElementFlags : byte` defines Fire, Ice, Thunder, Water and Holy as bits 0–4.

Writable known bits:

- `+0x11`: elemental Strike mask;
- `+0x12`: elemental Absorb mask;
- `+0x13`: elemental Immune/ignore mask;
- `+0x14`: elemental Resist mask;
- `+0x15`: elemental Weak mask.

For each byte, only bits `0x01|0x02|0x04|0x08|0x10` are changed. Bits `0x20|0x40|0x80` are preserved from the original byte even if present. The SOS byte at `+0x10`, all status/effect/stat/group/icon fields, text references, unknown data and trailing strings remain opaque/read-only.

This is intentionally **not** a general auto-ability editor.

### `ctb_base.bin` — battle timing

Path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/ctb_base.bin`

Each record is two bytes:

- `+0x00`: tick speed (`u8`);
- `+0x01`: ICV bonus (`u8`).

Derived timing ranges shown by the UI are not stored separately.

### `prepare.bin` — Rikku Mix results

Path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/prepare.bin`

Each record is `0xE0` bytes containing 112 little-endian `u16` result command IDs. Record ordinal represents the first ingredient; partner slot represents the second. Only selected result cells are written.

### `item_shop.bin` — item-shop inventories

Path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_shop.bin`

Each record is `0x22` bytes. The leading `u16` legacy rate is displayed read-only; the following sixteen `u16` item/command IDs are editable.

### `arms_shop.bin` — gear-shop inventories

Path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_shop.bin`

Same proved `0x22`-byte layout: read-only leading rate plus sixteen editable gear indices.

### FFX ability-animation family

English/US paths:

- `FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/command.bin`
- `FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/item.bin`
- `FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/monmagic1.bin`
- `FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/monmagic2.bin`

`FFXDataParser` and `osdanova/FFXProjectEditor` independently agree on the narrow animation surface:

- `command.bin`: `0x60`-byte records;
- `item.bin`: `0x60`-byte records;
- `monmagic1.bin`: `0x5C`-byte records;
- `monmagic2.bin`: `0x5C`-byte records;
- animation ID 1: `u16` at `+0x10`;
- animation ID 2: `u16` at `+0x12`.

Everything else—including text references, combat properties, unknown fields and trailing localized strings—is preserved. The API accepts only the four fixed table keys and rejects extra edit fields. One **FFX Abilities** UI selector covers the four fixed tables; there is no arbitrary path/file selector.

## FFX-2 fixed-record container

FFX-2 uses a separate generic container:

- minimum index: `u32` at `0x0C`;
- maximum index: `u32` at `0x10`;
- record size: `u32` at `0x14`;
- fixed-record bytes: `u32` at `0x18`;
- `0x1C..0x1F` opaque;
- records begin at `0x20`;
- all trailing bytes are preserved.

### FFX-2 `command.bin` — ability animation IDs

Path:

`FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/command.bin`

Record length is `0x8C`. String offset/key pairs at `+0x00..+0x07` are read-only context. Only animation IDs at `+0x08` and `+0x0A` are editable.

### FFX-2 `accessory.bin` — base abilities and price

Path:

`FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/accessory.bin`

`HeartlessSeph/FFX2-010-Templates` independently establishes zero-based `0x54`-byte records. Lexeditor writes only:

- four base ability IDs at `+0x18..+0x1F`;
- `u32` base price at `+0x20..+0x23`.

The `+0x24..+0x53` creature extension, string references, unknown bytes and trailing strings remain opaque.

## Structured write guarantees

The plugin currently exposes **14 proved structured tables**: twelve FFX tables and two FFX-2 tables.

Every structured save is guarded by:

- installed source VBF header MD5; and
- SHA-256 of the exact table bytes shown to the editor.

Concurrent source/project changes therefore fail closed. Saves create or atomically replace only project-overlay files; installed VBFs are never rewritten.

## Project and Fahrenheit deployment boundary

Project roots:

- FFX: `<project>/efl/x/<canonical FFX virtual path>`
- FFX-2: `<project>/efl/x2/<canonical FFX-2 virtual path>`

Deploy creates one Lexeditor-owned Fahrenheit file-only mod under `fahrenheit/mods/lexeditor-ffx-x2`, preserves unrelated load-order entries, and refuses to overwrite a foreign or externally changed deployment. Revert removes only an unchanged Lexeditor-owned deployment.

## Collection-aware Play boundary

Fahrenheit Stage 0 accepts `fhstage0.exe {EXECUTABLE_TO_LAUNCH} {ARGS}` and resolves `fhstage1.dll` relative to its working directory. Lexeditor therefore fixes cwd to `<game>/fahrenheit/bin` and exposes exactly two choices:

- `x` → `..\..\FFX.exe`
- `x2` → `..\..\FFX-2.exe`

It requires `fhstage0.exe`, `fhstage1.dll` and the selected game executable. Actual process creation is refused on non-Windows hosts.

`POST /api/play` accepts exactly `{"game":"x"}` or `{"game":"x2"}`—no executable, path, command, launcher selection, arguments or additional keys. `FFX&X-2_LAUNCHER.exe` is never used by Lexeditor Play.

## Read-only real-install verifier

CI cannot prove the actual Steam inventory, so `games.ffx_x2.verify_install` turns that requirement into a deterministic read-only check.

Typical run:

```powershell
python -m games.ffx_x2.verify_install --game-root "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster"
```

Draft-exit baseline with Fahrenheit prerequisites, machine-readable output and complete VBF SHA-256 hashes:

```powershell
python -m games.ffx_x2.verify_install --game-root "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster" --require-fahrenheit --hash-archives --json
```

The verifier:

- validates both installed VBF indexes;
- resolves raw/virtual path spellings;
- reads and validates all 14 currently supported structured tables with the production parsers;
- reports source paths, table SHA-256 values, record counts/sizes and VBF header metadata;
- optionally streams each complete VBF through SHA-256 with `--hash-archives`;
- reports Fahrenheit launch prerequisites;
- performs **no project write, deployment, VBF rewrite or game launch**.

A verifier pass proves inventory/layout compatibility only. It does not prove real EFL replacement loading or Stage 0 startup.

## Installed-game theme boundary

Lexeditor may derive bounded cosmetic assets from the user's own installed VBFs and optional `metamenu.vbf`. Browser-ready assets may be cached privately; recognized non-browser-ready font atlases, textures and FMOD banks may be cached for later conversion. No proprietary theme asset is committed, and theme extraction is never an editing/deployment readiness gate.

## Current coverage

Integrated:

- Steam collection discovery.
- Validated read-only indexing/decompression of both VBFs.
- Raw VBF path → canonical Fahrenheit EFL normalization.
- Searchable archive browser and byte-exact project extraction.
- Twelve FFX structured tables: treasure rewards, two price tables, auto-ability elemental masks, CTB timing, Mix results, two shop tables, and four ability-animation tables.
- Two FFX-2 structured tables: command animation IDs and accessory base abilities/price.
- Exact VBF/table stale-write guards and project-only saves.
- Reversible Fahrenheit file-only deployment.
- Fixed collection-aware Stage 0 Play actions.
- Private installed-game theme cache.
- Read-only real-install inventory/layout verifier with optional full VBF hashing.
- Evidence-based Data Map.

Not yet integrated/proved:

- Other FFX kernel formats or any unproved fields in `a_ability.bin` / the four ability tables.
- FFX localized dialogue/string editing.
- Other FFX-2 structured tables, localized string editing, creature-extension accessory fields or non-US variants.
- Conversion of recognized proprietary font/texture/audio formats that are not browser-ready.
- Installing/updating Fahrenheit itself.
- Real installed-game EFL acceptance and real Stage 0 startup through Lexeditor.

Synthetic/API/CI tests prove parser, service, project, deployment and launch-route mechanics. They do not substitute for the remaining real installed-game and in-game acceptance checks.
