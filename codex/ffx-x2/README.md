# FINAL FANTASY X/X-2 HD Remaster — Steam collection

## Product boundary

- Steam app ID: `359870`.
- Common install directory: `FINAL FANTASY FFX&FFX-2 HD Remaster`.
- Launcher: `FFX&X-2_LAUNCHER.exe`.
- Game executables: `FFX.exe` and `FFX-2.exe`.
- Primary archives: `data/FFX_Data.vbf` and `data/FFX2_Data.vbf`.

Lexeditor treats both games as one plugin because Steam ships them as one collection and Fahrenheit supports both archives from one framework installation.

## VBF read contract

The integrated VBF reader is intentionally read-only. The archive format is established from `michivi/vbf-fs`:

1. ASCII signature `SRYK`.
2. 32-bit little-endian header length.
3. 64-bit little-endian file count.
4. 16-byte MD5 path hash per file.
5. 32-byte file entry records: start block, reserved word, uncompressed byte count, data offset, name-table offset.
6. Length-prefixed NUL-terminated name table.
7. 16-bit block descriptors for 64 KiB logical blocks.
8. File payload blocks, with non-final nonzero descriptors representing zlib-compressed byte lengths; a short final descriptor equal to the final logical length is a raw partial block; zero is a full passthrough block.
9. Final 16 bytes are the MD5 of the complete header.

The reader validates the signature, header hash, per-path MD5, table boundaries, data offsets, path safety and decompressed lengths before exposing an entry.

Real archive names may omit the game-facing virtual archive root. Lexeditor therefore resolves both `ffx_ps2/...` and `FFX_Data/ffx_ps2/...` source spellings, but always stages FFX replacements beneath the canonical Fahrenheit path `efl/x/FFX_Data/...` (and equivalently `efl/x2/FFX2_Data/...` for FFX-2).

## FFX fixed-record table contract

`FFXDataParser` was used as a research cross-check for the common FFX kernel-table container. Lexeditor's implementation is independent and only encodes the observed format facts:

- minimum record index: little-endian `u16` at `0x08`;
- maximum record index: little-endian `u16` at `0x0A`;
- fixed record size: little-endian `u16` at `0x0C`;
- total fixed-record bytes: little-endian `u16` at `0x0E`;
- fixed records begin at `0x14`;
- bytes after the fixed-record region are opaque trailing data and are preserved exactly.

Lexeditor rejects inconsistent index ranges, zero record sizes, mismatched record byte counts and truncated record regions instead of guessing.

### `takara.bin` treasure rewards

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin`

For each fixed-size treasure record, only these proved fields are interpreted or changed:

- `+0x00`: reward kind (`u8`)
  - `0x00` = gil
  - `0x02` = item/command
  - `0x05` = gear pickup
  - `0x0A` = key item
- `+0x01`: quantity (`u8`); gil uses `quantity × 100`.
- `+0x02..+0x03`: reward type ID (`u16`, little-endian).

Unknown reward kinds remain representable. Any bytes after `+0x03` in a record are preserved byte-for-byte.

### `item_rate.bin` item/command prices

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_rate.bin`

Each proved record is exactly four bytes containing one little-endian unsigned `u32` gil price. `FFXDataParser` maps table order to item/command IDs beginning at `0x2000`; Lexeditor exposes both the source record ID and that derived command ID and writes only selected four-byte price records.

### `arms_rate.bin` auto-ability prices

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_rate.bin`

This is the same proved four-byte unsigned gil-price table shape. `FFXDataParser` applies the rows by ordinal to auto-ability IDs displayed as `80xx`, so Lexeditor maps ordinal 0 to `0x8000`, ordinal 1 to `0x8001`, and so on. Item prices and auto-ability prices share one binary u32-price implementation while exposing their different semantic ID fields.

### `ctb_base.bin` battle timing

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/ctb_base.bin`

Each proved record is exactly two bytes:

- `+0x00`: tick speed (`u8`).
- `+0x01`: ICV bonus (`u8`).

The source tool labels each row as `Agility = record index + 1`. Lexeditor also shows the derived initial CTB range used by that research model: maximum ICV = `tick speed × 3`; minimum ICV = maximum ICV − ICV bonus. Only the two source bytes are written.

### `prepare.bin` Rikku Mix results

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/prepare.bin`

Each proved record is exactly `0xE0` bytes: 112 little-endian `u16` result command IDs, one for each possible second ingredient. `FFXDataParser` maps record ordinal to the first ingredient command ID `0x2000 + ordinal`, and partner slot `i` to the second ingredient command ID `0x2000 + i`. Lexeditor edits only selected 16-bit result cells; zero remains a valid/undefined result value.

### `item_shop.bin` inventories

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_shop.bin`

The proved record length is `0x22` bytes:

- `+0x00..+0x01`: legacy/unused rate field (`u16`). Lexeditor displays it but does not edit it because its gameplay semantics are not established.
- `+0x02..+0x21`: sixteen item/command IDs (`u16`, little-endian), one per shop slot.

Lexeditor writes only explicitly changed inventory slots and preserves the leading rate field byte-for-byte.

### `arms_shop.bin` gear inventories

Integrated path:

`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_shop.bin`

This table uses the same proved `0x22`-byte shop record shape:

- `+0x00..+0x01`: legacy/unused rate field (`u16`), displayed read-only.
- `+0x02..+0x21`: sixteen gear indices (`u16`, little-endian), one per shop slot.

Item and gear shops share one validated binary implementation; their public APIs remain semantic (`itemIds` versus `gearIds`). Lexeditor writes only explicitly changed slots and preserves the leading rate field byte-for-byte.

## FFX-2 fixed-record table contract

FFX-2 uses a different generic fixed-record container. `FFXDataParser.readGenericX2DataFile` establishes the fields Lexeditor currently validates:

- minimum record index: little-endian `u32` at `0x0C`;
- maximum record index: little-endian `u32` at `0x10`;
- fixed record size: little-endian `u32` at `0x14`;
- total fixed-record bytes: little-endian `u32` at `0x18`;
- bytes `0x1C..0x1F` remain opaque;
- fixed records begin at `0x20`;
- bytes after the fixed-record region, including localized string data, are preserved exactly.

Lexeditor validates the index range, record size/count arithmetic and record-region boundary before exposing an X-2 table. It does not reuse the FFX `u16` header parser.

### `command.bin` ability animation IDs

Integrated English/US path:

`FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/command.bin`

The proved fixed record length is `0x8C` bytes. The research model identifies:

- `+0x00..+0x01`: name string offset (`u16`), read-only in Lexeditor;
- `+0x02..+0x03`: name string key (`u16`), read-only;
- `+0x04..+0x05`: description string offset (`u16`), read-only;
- `+0x06..+0x07`: description string key (`u16`), read-only;
- `+0x08..+0x09`: animation ID 1 (`u16`), editable;
- `+0x0A..+0x0B`: animation ID 2 (`u16`), editable.

Lexeditor deliberately does **not** decode or rewrite FFX-2 strings yet. A save patches only `+0x08..+0x0B` in selected records and preserves every other byte, including all unknown record fields and the trailing localized strings.

All eight structured editors are guarded by the relevant source VBF header MD5 and the SHA-256 of the exact table bytes shown to the editor. A concurrent project or source change causes a conflict instead of an overwrite.

## Project and loader boundary

The project contains only replacement files:

- `<project>/efl/x/<canonical FFX virtual path>` for FFX.
- `<project>/efl/x2/<canonical FFX-2 virtual path>` for FFX-2.

For example, a raw FFX VBF entry `ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin` is staged as
`<project>/efl/x/FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin`.
A raw FFX-2 entry `ffx_ps2/ffx2/master/new_uspc/battle/kernel/command.bin` is staged as
`<project>/efl/x2/FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/command.bin`.

Structured editors read the staged project file when one exists; otherwise they read the installed VBF entry. A save creates or atomically replaces only the project override. Installed VBF bytes remain untouched.

Deploy Project creates one file-only Fahrenheit mod at
`<game>/fahrenheit/mods/lexeditor-ffx-x2/`, writes its manifest, copies the project EFL tree, and adds exactly one `lexeditor-ffx-x2` line to `fahrenheit/mods/loadorder` while preserving every other line. Revert removes only the unchanged Lexeditor-owned mod and that load-order entry.

Deployment refuses to overwrite a pre-existing foreign directory or a Lexeditor deployment changed outside Lexeditor.

## Installed-game theme boundary

Lexeditor can derive bounded cosmetic assets from the user's own installed VBFs and optional `data/metamenu.vbf`. The private cache may expose browser-ready title/menu PNGs, web fonts or audio when those formats already exist, while recognizing/caching non-browser-ready font atlases, UI textures and FMOD banks for later conversion work. No proprietary theme asset is committed to Lexeditor, and theme extraction is never a readiness gate for editing or deployment.

## Current coverage

Integrated:

- Steam collection discovery.
- Validation and indexing of both VBF archives.
- Raw/virtual archive path normalization into canonical Fahrenheit EFL paths.
- Path search and byte-exact extraction/decompression.
- Safe extraction to a project overlay without overwriting edited project data.
- Common FFX fixed-record table validation.
- Structured FFX `takara.bin` treasure reward editing.
- Structured FFX `item_rate.bin` item/command gil-price editing.
- Structured FFX `arms_rate.bin` auto-ability gil-price editing.
- Structured FFX `ctb_base.bin` tick-speed / ICV-bonus editing.
- Structured FFX `prepare.bin` Rikku Mix result editing.
- Structured FFX `item_shop.bin` 16-slot item/command inventory editing.
- Structured FFX `arms_shop.bin` 16-slot gear inventory editing.
- FFX-2 `u32` fixed-record table validation.
- Conservative FFX-2 `command.bin` animation-ID editing for the `new_uspc` table.
- Reversible file-only Fahrenheit deployment mechanics for both `efl/x` and `efl/x2` project trees.
- Private installed-game cosmetic theme extraction/cache with safe fallback.
- Evidence-based Data Map.

Not yet integrated:

- Other FFX gameplay/kernel record editors.
- FFX dialogue/text editing.
- Other FFX-2 structured tables, localized string editing, or non-US command-table variants.
- Conversion of recognized proprietary font/texture/audio formats that are not already browser-ready.
- Installing/updating Fahrenheit itself.
- Choosing FFX vs FFX-2 when launching through Fahrenheit from Lexeditor.
- Live installed-game acceptance for replacement loading.

Synthetic/API tests prove parser, service, project and deployment mechanics. They do not prove that a real Steam build accepts a given replacement file in-game.
