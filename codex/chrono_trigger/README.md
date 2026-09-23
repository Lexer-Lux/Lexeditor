# Chrono Trigger Steam

## Edition boundary

Lexeditor's active Chrono Trigger target is the Steam release. SNES and DS editors are research references only. Never transfer ROM offsets, pointer widths, event widths, or packed fields into the Steam plugin without independent PC evidence.

## Current evidence set

| Source | Revision audited | License | Steam value |
| --- | --- | --- | --- |
| CTViewer | `2e5a206e09f0028fd5a1ca6cb9a9ed18bfc64fea` | MIT | Primary PC archive, exit, treasure, scene/world format reference |
| ct_nx | `e6bc0b4b032df2dbc62a6f142fe08ae0470b61fe` | MIT | ARC1/CTP corroboration; CTP = ZIP of archive-relative replacements |
| Temporal Redux | `d8d4e38c0bf08b51a29441ef7ea2a489d63da58f` | GPLv3 | Event-editor research only; no code reused |
| CTNx | `fda83d565897737d9853cb5ba0b4e7e5d87aa674` | GPLv3 | Reimplementation research only |
| ChronoMod | `4566e9dea7a3510cbb442991cd9efa223b95fdc7` | no clear top-level repo license found | Historical ARC1 corroboration only |
| CTExt | `892c47166c56f6d20a2c805c303586096e8d466a` | no clear top-level repo license found | Runtime CTP/loose-file behavior only; not bundled |

`ui/component-catalog.js` was requested as a reference but is unavailable on current master. `plugins/blank/editor.html`, `docs/UI-MANUAL.md`, and the RDR2/FF9 Table+Detail implementations are the current UI references.

## Proven Steam layouts used by the fresh replacement

### resources.bin / ARC1

- 16-byte XOR-obfuscated header.
- decoded signature `ARC1`.
- little-endian file size, index offset and encoded index size.
- index and resources are individually XOR-obfuscated using an absolute-offset-seeded LCG.
- decoded block starts with a big-endian uncompressed size followed by gzip data.
- decompressed index starts with a little-endian entry count, then 12-byte records `(pathOffset, dataOffset, storedSize)`; path offsets are absolute into that decompressed index buffer.

Lexeditor validates declared file size and bounds, applies decoded-size caps, and never rebuilds the installed archive.

### CTP

A CTP is a normal ZIP. Each member path equals the `resources.bin` path it replaces. The fresh plugin emits deterministic sorted members and only changed `Game/...` / `Localize/...` resources.

### MapJump area exits (PC)

- `Game/common/MapJumpOffsetTbl.dat`: `u32 count`, then `count * u16` offsets. PC byte offset is `stored * 8 + 4`.
- `Game/common/MapJumpDataTbl.dat`: 8-byte records: `u8 x`, `u8 y`, `u8 size/orientation`, `u8 facing/shift flags`, `u16 destination`, `u8 targetX`, `u8 targetY`.
- size low 7 bits = length minus one; bit 7 selects vertical vs horizontal.
- facing low two bits map Up/Down/Left/Right; bits 2/3 apply the documented half-tile destination shifts; upper four bits remain unmodelled and must be preserved.
- destinations `0x1F0..0x1FF` select world maps; others are scene destinations within the editor's allowed `0..0x1FF` range.

### Takara treasure (PC)

- `Game/common/TakaraOffsetTbl.dat`: `u32 count`, then `count * u16`; PC byte offset is `stored * 6 + 4`.
- `Game/common/TakaraDataTbl.dat`: 6-byte records: `u8 x`, `u8 y`, `u16 contents`, `u16 trailing`.
- `x=0,y=0` redirects treasure lookup to another scene using `contents`; the fresh editor keeps these alias records read-only.
- content high bit indicates gold, stored in increments of two.
- non-gold category prefixes: `0000` weapon, `1000` armor, `2000` helmet, `3000` accessory, `4000` consumable, `5000` item; low 9 bits are the category-local index.
- the final `u16` has no assigned semantics in the evidence used here and is preserved exactly.

## Historical failure boundary

Merged PR #454 is not the architecture to continue. It became broad and research-heavy before it delivered enough practical editing. Its code is historical evidence only. Fresh work should prefer useful fixed-size/typed formats with synthetic roundtrip tests and CTP output before adding expensive runtime-research surfaces.

### Mapinfo area headers (PC)

Each `Game/field/Mapinfo/mapinfo_<scene>.dat` starts with a fixed 24-byte PC header: nine modeled `u16` references (music, L1/L2 tileset, L1/L2 assembly, L3 tileset, palette, palette animation, map, chip animation, event script), one unmodelled PC `u16`, then four raw camera-mask bytes. CTViewer treats `scrollLeft == 0x80` as the disabled/full-map camera sentinel. Lexeditor preserves the unmodelled word and all trailing bytes; it does not transfer the shorter SNES header layout.

### Fixed PC palettes

Current-PC field and world palette files are read by CTViewer after skipping a two-byte prefix, then reading exactly 256 little-endian 15-bit colors. Bits 0–4 are red, 5–9 green, and 10–14 blue; the audited renderer ignores bit 15. Lexeditor edits only those RGB components, preserving the two-byte prefix, each color's bit 15, and any trailing bytes.
