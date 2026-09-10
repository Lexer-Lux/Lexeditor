# FINAL FANTASY X/X-2 HD Remaster — Steam collection

## Product boundary

- Steam app ID: `359870`.
- Common install directory: `FINAL FANTASY FFX&FFX-2 HD Remaster`.
- Collection launcher present in the install: `FFX&X-2_LAUNCHER.exe`.
- Game executables: `FFX.exe` and `FFX-2.exe`.
- Primary archives: `data/FFX_Data.vbf` and `data/FFX2_Data.vbf`.

Lexeditor treats both games as one plugin because Steam ships them as one collection and Fahrenheit supports both archives from one framework installation. Play intentionally bypasses the Square Enix collection launcher and targets each game through Fahrenheit Stage 0 directly.

## VBF read contract

The integrated VBF reader is intentionally read-only. The format is established from `michivi/vbf-fs`:

1. ASCII signature `SRYK`.
2. 32-bit little-endian header length.
3. 64-bit little-endian file count.
4. 16-byte MD5 path hash per file.
5. 32-byte file-entry records: start block, reserved word, uncompressed byte count, data offset, name-table offset.
6. Length-prefixed NUL-terminated name table.
7. 16-bit block descriptors for 64 KiB logical blocks.
8. File payload blocks, including zlib-compressed blocks and passthrough blocks.
9. Final 16 bytes: MD5 of the complete header.

The reader validates signature, header hash, per-path MD5, table boundaries, data offsets, path safety and decompressed lengths before exposing an entry.

Real archive names may omit the game-facing virtual archive root. Lexeditor resolves both `ffx_ps2/...` and `FFX_Data/ffx_ps2/...` source spellings, but always stages FFX replacements beneath canonical Fahrenheit path `efl/x/FFX_Data/...`; FFX-2 equivalently uses `efl/x2/FFX2_Data/...`.

## FFX fixed-record table contract

`FFXDataParser` is a research cross-check for the common FFX kernel-table container. Lexeditor independently implements only these format facts:

- minimum record index: little-endian `u16` at `0x08`;
- maximum record index: little-endian `u16` at `0x0A`;
- fixed record size: little-endian `u16` at `0x0C`;
- total fixed-record bytes: little-endian `u16` at `0x0E`;
- fixed records begin at `0x14`;
- bytes after the fixed-record region remain opaque and are preserved exactly.

Lexeditor rejects inconsistent index ranges, zero record sizes, mismatched record-byte counts and truncated record regions instead of guessing.

### `takara.bin` treasure rewards

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin`

Only these proved fields are editable:

- `+0x00`: reward kind (`u8`): `0x00` gil, `0x02` item/command, `0x05` gear, `0x0A` key item.
- `+0x01`: quantity (`u8`); gil uses `quantity × 100`.
- `+0x02..+0x03`: reward type ID (`u16`).

Unknown kinds stay representable; all other bytes are preserved.

### `item_rate.bin` item/command prices

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_rate.bin`

Each proved record is one little-endian `u32` gil price. Table ordinal maps to command/item IDs beginning at `0x2000`. Only selected four-byte prices are written.

### `arms_rate.bin` auto-ability prices

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_rate.bin`

This uses the same four-byte `u32` price-table shape, with ordinal zero mapped to auto-ability ID `0x8000`. It shares the validated price implementation with `item_rate.bin` while retaining separate semantic IDs.

### `ctb_base.bin` battle timing

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/ctb_base.bin`

Each record is exactly two bytes:

- `+0x00`: tick speed (`u8`).
- `+0x01`: ICV bonus (`u8`).

The UI also derives the researched initial-CTB range, but only those two source bytes are written.

### `prepare.bin` Rikku Mix results

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/prepare.bin`

Each record is `0xE0` bytes: 112 little-endian `u16` result command IDs. Record ordinal is first ingredient `0x2000 + ordinal`; partner slot `i` is second ingredient `0x2000 + i`. Only explicitly changed result cells are written.

### `item_shop.bin` inventories

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_shop.bin`

Each record is `0x22` bytes:

- `+0x00..+0x01`: legacy rate (`u16`), displayed read-only because its gameplay semantics are unproved.
- `+0x02..+0x21`: sixteen item/command IDs (`u16`).

Only selected inventory slots are written.

### `arms_shop.bin` gear inventories

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_shop.bin`

This shares the proved `0x22`-byte shop layout with `item_shop.bin`: the leading rate remains read-only and only the sixteen gear-index slots can be changed.

### Ability animation family

Integrated English/US paths:

- `FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/command.bin`
- `FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/item.bin`
- `FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/monmagic1.bin`
- `FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/monmagic2.bin`

Two independent implementations agree on the narrow surface Lexeditor exposes.

`Karifean/FFXDataParser` models all four files with the same command-data class, reads animation ID 1 at record `+0x10` and animation ID 2 at `+0x12`, defines player-command records as `0x60` bytes, and defines monster-magic records as `0x5C` bytes. Its write paths use the `0x60` form for `command.bin` and `item.bin` and the `0x5C` form for `monmagic1.bin` and `monmagic2.bin`.

`osdanova/FFXProjectEditor` independently identifies the same four files under `new_uspc/battle/kernel`. Its serialized ability structure places four four-byte text-reference structures before `Anim1Id`/`Anim2Id`, independently confirming offsets `+0x10/+0x12`; command/item records include the four-byte player extension while monster magic does not.

Lexeditor therefore enforces:

- `command.bin`: `0x60`-byte records.
- `item.bin`: `0x60`-byte records.
- `monmagic1.bin`: `0x5C`-byte records.
- `monmagic2.bin`: `0x5C`-byte records.
- `+0x10..+0x11`: animation ID 1 (`u16`), editable.
- `+0x12..+0x13`: animation ID 2 (`u16`), editable.

Everything else—including text references, command properties, combat fields, unknown bytes and trailing localized strings—remains opaque and byte-preserved. The write API rejects unknown table names and extra edit fields.

The UI presents these as one **FFX Abilities** editor with an explicit fixed table selector, not as a generic file or hex editor.

## FFX-2 fixed-record table contract

FFX-2 uses a different generic fixed-record container. Lexeditor currently validates:

- minimum record index: little-endian `u32` at `0x0C`;
- maximum record index: little-endian `u32` at `0x10`;
- fixed record size: little-endian `u32` at `0x14`;
- total fixed-record bytes: little-endian `u32` at `0x18`;
- bytes `0x1C..0x1F` remain opaque;
- fixed records begin at `0x20`;
- all bytes after the record region are preserved exactly.

### `command.bin` ability animation IDs

Integrated English/US path:

`FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/command.bin`

The proved record length is `0x8C`. Lexeditor reads string offset/key pairs at `+0x00..+0x07` for context but edits only:

- `+0x08..+0x09`: animation ID 1 (`u16`).
- `+0x0A..+0x0B`: animation ID 2 (`u16`).

Every other byte and the localized string tail are preserved.

### `accessory.bin` base abilities and prices

Integrated English/US path:

`FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/accessory.bin`

The independent `HeartlessSeph/FFX2-010-Templates` reference establishes zero-based `0x54`-byte records. Lexeditor edits only:

- `+0x18..+0x1F`: four base ability IDs (`u16` each).
- `+0x20..+0x23`: base price (`u32`).

The `+0x24..+0x53` creature extension, string references and trailing strings remain opaque/read-only.

## Structured write guarantees

The plugin currently exposes **13 proved structured tables**: eleven FFX tables and two FFX-2 tables. Every structured save is guarded by both:

- the installed source VBF header MD5; and
- SHA-256 of the exact table bytes shown to the editor.

Concurrent source/project changes therefore fail closed instead of being overwritten. Saves create or replace only project-overlay files; installed VBFs are never rewritten.

## Project and loader boundary

Project replacement roots are:

- `<project>/efl/x/<canonical FFX virtual path>`
- `<project>/efl/x2/<canonical FFX-2 virtual path>`

For example, raw VBF path `ffx_ps2/ffx/master/new_uspc/battle/kernel/item.bin` is staged as:

`<project>/efl/x/FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/item.bin`

Deploy creates one Lexeditor-owned Fahrenheit file-only mod under `fahrenheit/mods/lexeditor-ffx-x2`, preserves unrelated load-order entries, and refuses to overwrite a foreign or externally changed deployment. Revert removes only an unchanged Lexeditor-owned deployment.

## Collection-aware Play boundary

Fahrenheit Stage 0 accepts `fhstage0.exe {EXECUTABLE_TO_LAUNCH} {ARGS}` and loads `fhstage1.dll` by relative name. Lexeditor therefore fixes the working directory to `<game>/fahrenheit/bin` and exposes exactly two choices:

- `x` → `[<game>/fahrenheit/bin/fhstage0.exe, "..\\..\\FFX.exe"]`
- `x2` → `[<game>/fahrenheit/bin/fhstage0.exe, "..\\..\\FFX-2.exe"]`

Before launch it requires `fhstage0.exe`, `fhstage1.dll` and the selected executable. Process creation is refused on non-Windows hosts.

The loopback API exposes `GET /api/launch`, launch readiness in `GET /api/dashboard`, and `POST /api/play`. `/api/play` accepts exactly `{"game":"x"}` or `{"game":"x2"}`. It accepts no executable, path, command, launcher selection, arguments or additional keys, and never launches `FFX&X-2_LAUNCHER.exe`.

## Read-only real-install verification

CI can validate synthetic archive/container behavior but cannot prove the actual Steam inventory. `games.ffx_x2.verify_install` exists specifically to turn the remaining real-install inventory check into a deterministic read-only operation.

Example:

```powershell
python -m games.ffx_x2.verify_install --game-root "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster"
```

Machine-readable report:

```powershell
python -m games.ffx_x2.verify_install --game-root "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster" --json
```

Also require Fahrenheit Stage 0, Stage 1 and both game executables to be present:

```powershell
python -m games.ffx_x2.verify_install --game-root "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster" --require-fahrenheit
```

The verifier:

- validates both installed VBF indexes and hashes;
- resolves raw versus canonical EFL spellings;
- reads/decompresses every one of the 13 currently supported structured tables;
- runs each table through the same strict parser used by the editor;
- reports record counts/sizes, source paths and exact table SHA-256 values;
- reports Fahrenheit launch prerequisites;
- performs **no project write, deployment, VBF rewrite, or game launch**.

A successful verifier run proves the installed inventory and supported record layouts match Lexeditor's expectations. It still does **not** prove that Fahrenheit accepts a replacement in-game or that Stage 0 successfully starts either title.

## Installed-game theme boundary

Lexeditor may derive bounded cosmetic assets from the user's own installed VBFs and optional `data/metamenu.vbf`. Browser-ready assets may be cached privately; recognized non-browser-ready font atlases, UI textures and FMOD banks may also be cached for later conversion. No proprietary theme asset is committed, and theme extraction is never an editor/deployment readiness gate.

## Current coverage

Integrated:

- Steam collection discovery and validated read-only VBF indexing/decompression.
- Raw VBF path → canonical Fahrenheit EFL normalization.
- Searchable archive browser and safe project extraction.
- Eleven FFX structured tables:
  - `takara.bin`
  - `item_rate.bin`
  - `arms_rate.bin`
  - `ctb_base.bin`
  - `prepare.bin`
  - `item_shop.bin`
  - `arms_shop.bin`
  - `new_uspc/battle/kernel/command.bin` animation IDs
  - `new_uspc/battle/kernel/item.bin` animation IDs
  - `new_uspc/battle/kernel/monmagic1.bin` animation IDs
  - `new_uspc/battle/kernel/monmagic2.bin` animation IDs
- Two FFX-2 structured tables: `command.bin` animation IDs and `accessory.bin` base abilities/price.
- Exact table/VBF stale-write guards and project-only saves.
- Reversible Fahrenheit file-only deployment.
- Fixed collection-aware Stage 0 Play actions.
- Private installed-game theme cache.
- Read-only real-install inventory/record-layout verifier.
- Evidence-based Data Map.

Not yet integrated/proved:

- Other FFX gameplay/kernel formats or any unproved fields in the four ability tables.
- FFX dialogue/localized string editing.
- Other FFX-2 structured tables, localized string editing, creature-extension accessory fields, or non-US variants.
- Conversion of recognized proprietary font/texture/audio formats that are not browser-ready.
- Installing/updating Fahrenheit itself.
- Real in-game EFL replacement acceptance and real Stage 0 startup through Lexeditor.

Synthetic/API/CI tests prove parser, service, project, deployment and launch-route mechanics. They do not substitute for the remaining real installed-game and in-game acceptance checks.
