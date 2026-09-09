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

Unknown reward kinds remain representable. Any bytes after `+0x03` in a record are preserved byte-for-byte. Saving is guarded by the VBF header MD5 and the SHA-256 of the exact `takara.bin` bytes shown to the editor, so a concurrent external change causes a conflict rather than an overwrite.

## Project and loader boundary

The project contains only replacement files:

- `<project>/efl/x/<VBF path>` for FFX.
- `<project>/efl/x2/<VBF path>` for FFX-2.

This mirrors Fahrenheit's External File Loader exactly. For example, an archive entry such as
`FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin` becomes
`<project>/efl/x/FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin`.

Structured editors follow the same boundary. They read the staged project file when one exists; otherwise they read the installed VBF entry. A save creates or atomically replaces only the project override. Installed VBF bytes remain untouched.

Deploy Project creates one file-only Fahrenheit mod at
`<game>/fahrenheit/mods/lexeditor-ffx-x2/`, writes its manifest, copies the project EFL tree, and adds exactly one `lexeditor-ffx-x2` line to `fahrenheit/mods/loadorder` while preserving every other line. Revert removes only the unchanged Lexeditor-owned mod and that load-order entry.

Deployment refuses to overwrite a pre-existing foreign directory or a Lexeditor deployment changed outside Lexeditor.

## Current coverage

Integrated:

- Steam collection discovery.
- Validation and indexing of both VBF archives.
- Path search and byte-exact extraction/decompression.
- Safe extraction to a project overlay without overwriting an edited project file.
- Common FFX fixed-record table validation.
- Structured FFX `takara.bin` treasure reward editing.
- Reversible file-only Fahrenheit deployment mechanics.
- Evidence-based Data Map.

Not yet integrated:

- Other FFX gameplay/kernel record editors.
- Dialogue/text editing.
- FFX-2 structured tables.
- Texture/model/audio formats.
- Installing/updating Fahrenheit itself.
- Choosing FFX vs FFX-2 when launching through Fahrenheit from Lexeditor.
- Live installed-game acceptance for replacement loading.

Synthetic/API tests prove parser, service, project and deployment mechanics. They do not prove that a real Steam build accepts a given replacement file in-game.
