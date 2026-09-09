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

All three structured editors are guarded by the VBF header MD5 and the SHA-256 of the exact table bytes shown to the editor. A concurrent project or source change causes a conflict instead of an overwrite.

## Project and loader boundary

The project contains only replacement files:

- `<project>/efl/x/<canonical FFX virtual path>` for FFX.
- `<project>/efl/x2/<canonical FFX-2 virtual path>` for FFX-2.

For example, a raw VBF entry `ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin` is staged as
`<project>/efl/x/FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin`.

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
- Structured FFX `item_shop.bin` 16-slot item/command inventory editing.
- Structured FFX `arms_shop.bin` 16-slot gear inventory editing.
- Reversible file-only Fahrenheit deployment mechanics.
- Private installed-game cosmetic theme extraction/cache with safe fallback.
- Evidence-based Data Map.

Not yet integrated:

- Other FFX gameplay/kernel record editors.
- Dialogue/text editing.
- FFX-2 structured tables.
- Conversion of recognized proprietary font/texture/audio formats that are not already browser-ready.
- Installing/updating Fahrenheit itself.
- Choosing FFX vs FFX-2 when launching through Fahrenheit from Lexeditor.
- Live installed-game acceptance for replacement loading.

Synthetic/API tests prove parser, service, project and deployment mechanics. They do not prove that a real Steam build accepts a given replacement file in-game.
