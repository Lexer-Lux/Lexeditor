# Chrono Trigger Steam format evidence ledger

This file records why Lexeditor treats a Steam structure as writable, read-only, or unresolved. The purpose is to prevent SNES/DS assumptions or another tool's renderer behavior from being silently promoted to current-PC semantics.

## Evidence classes

- **Proven PC layout** — current-PC parser/constructor/menu evidence or independent round trips establish byte boundaries and operand meaning. Fixed-width writes may be enabled when invariants are tested.
- **Structural PC evidence** — boundaries/fields are known, but runtime semantics or write behavior are not. Read-only.
- **Renderer behavior only** — a viewer implements something, but Steam runtime equivalence is not proven.
- **Candidate only** — path/name/size evidence without a verified record layout.

When sources conflict, a platform-specific PC parser/override is stronger boundary evidence than a generic menu or SNES-oriented constructor. A menu can still establish operand semantics when its PC encoding is internally reversible and consistent with the PC width table.

## ARC1 `resources.bin`

**Status: proven container; Vanilla remains immutable.**

ChronoMod establishes the ARC1 header/index, offset-keyed XOR stream, gzip-wrapped entries and replacement/rebuild mechanics. Lexeditor uses an independent reader and keeps installed `resources.bin` read-only; normal writes are CTExt loose-file/CTP overrides.

ARC1 resource blocks also expose a decoded four-byte big-endian uncompressed-size prefix before the gzip stream. Lexeditor may inspect that size without inflating the payload. This is resource metadata, not gameplay-field evidence.

ChronoMod does not provide enemy/item/tech/battle record parsers, so it is evidence for the container only.

## Field events (`Game/field/atel/Atel_*.dat`)

**Status: PC structural parser + growing proven fixed-width operand set.**

Temporal Redux supplies explicit `Platform.PC` width overrides, a platform-aware command parser, command tables, constructors and live editor menus. Lexeditor exposes a named writer only when the current command can be rewritten at exactly the same width and the relevant PC operand meaning is explicit.

### Proven families

- `0x12`/`0x13`: `/2` script-memory slot vs immediate u8/u16, comparison op 0–7, jump-if-false byte.
- `0x14`/`0x15`: two `/2` script-memory slots, comparison op 0–7, jump-if-false byte; opcode selects 8/16-bit width.
- `0x16`: bank-7F 8-bit comparison. The constructor emits `[addressLow, value, operation|pageBit, jump]`, restricts the address to `0x7F0000–0x7F01FF`, stores the comparator in bits 0–2 and uses bit 7 to select the upper `0x100`-byte page. Lexeditor rejects stored operator bytes with any undocumented bits 3–6 set.
- `0x18`: storyline threshold + jump byte.
- Button/action checks `0x2D`, `0x30/31`, `0x34–39`, `0x3B/3C`, `0x3F–44`: opcode fixes the check/mode; the sole argument is the failure jump distance.
- `0x02–07`: doubled object/PC target + packed `priority<<4 | functionId`; opcode fixes continue/sync/halt.
- `0x0A`, `0x0B`, `0x0C`, `0x7C`, `0x7D`: live menus/constructors store `objectId*2`. `0x0B/0x0C` edit only the target; opcode keeps processing off/on fixed.
- `0x0D/0x0E`: constructors define only bits 0–1 (`through walls`, `through PCs`, `onto tile`, `onto object`). Lexeditor changes only those bits and preserves all higher unknown bits.
- `0x19`: result -> one `/2` script-memory slot.
- `0x1C`: live `GetResultMenu` decodes the stored byte as `0x7F0000 + byte`; writable range is therefore only `0x7F0000–0x7F00FF`.
- `0x4F/0x50`: immediate u8/u16 -> `/2` script-memory destination.
- `0x51/0x52`: `/2` script-memory source -> `/2` script-memory destination, 8/16-bit.
- `0x53/0x54`: u16 offset from `0x7F0000` -> `/2` script-memory destination, 8/16-bit. Temporal Redux chooses these only when `is_local_mem()` is true, so Lexeditor limits the bank side to `0x7F0000–0x7F01FF`; wider encoded offsets remain read-only.
- `0x56`: u8 immediate -> u16 offset from `0x7F0000`; full encodable bank range is `0x7F0000–0x7FFFFF`.
- `0x58/0x59`: `/2` script-memory source -> u16 bank offset, 8/16-bit. As with `0x53/0x54`, the constructor selects these only for `0x7F0000–0x7F01FF`.
- `0x5B`, `0x5D/0x5E`, `0x5F`, `0x71/0x72/0x73`: explicit local script-memory add/subtract/increment/decrement forms.
- `0x1E/0x1F/0x25/0x26`: live `SetFacingMenu` fixes Up/Down/Left/Right in the opcode and writes `NPC ID * 2`. The live menu exposes NPC IDs `0x00–0x32`, so larger even encodings remain read-only.
- `0x23/0x24`: live `GetFacingMenu` fixes object vs PC by opcode and writes `targetId*2` plus a `/2` script-memory result destination.
- `0xA8/0xA9`: live `FaceObjectMenu` fixes object vs PC by opcode and writes `targetId*2`.
- `0x63/0x64`: bit index 0–7 + `/2` script-memory slot.
- `0x65/0x66`: bank-7F Set/Reset Bit. Constructor/table agree that bits 0–2 hold the bit index, bit 7 adds `0x100` to the low address byte, and the address domain is `0x7F0000–0x7F01FF`. Lexeditor accepts only canonical first bytes `00–07` or `80–87`; undocumented bits 3–6 fail closed.
- `0x69`/`0x6B`: raw u8 bitmask + `/2` script-memory slot.
- `0x6F`: right-shift count 0–7 + `/2` script-memory slot.
- PC-only `0x3A`, `0x3D`, `0x3E`, `0x45`, `0x46`, `0x70`, `0x74`, `0x78`: explicit PC factories + width overrides establish two one-byte operands. They remain raw local/extended/party slot bytes because the PC factories do not use the ordinary `get_offset()` helper.
- PC-only `0x6E`: factory and PC width override establish `[extendedSlot, u8 value, comparison op, jump]`. The extended slot stays a raw byte; Lexeditor does not invent an address mapping. Comparison op is restricted to the same proven 0–7 enum and the final byte is validated as a jump-if-false distance.
- `0x7A`: live `JumpMenu` and table agree on X byte, Y byte and a third `height/speed` byte. Lexeditor does not invent pixel/tile units or separate height vs speed semantics.
- `0x8F`, `0x94/95`, `0x96/97`, `0x98/99`, `0x9A`, `0xA0/A1`, `0xB5/B6`: live movement/follow constructors agree on operand order. Direct X/Y values remain labeled coordinate bytes unless units are independently proven.
- `0x9D`: live `VectorMoveFromMemMenu` writes two `/2` script-memory sources, direction then magnitude, and decodes them inversely.
- `0xD9`: six literal party coordinate bytes: PC1 X/Y, PC2 X/Y, PC3 X/Y.
- `0xE2`: four `/2` script-memory sources for location, X, Y and facing. `0x7F0400` is rejected because one slot byte ends at `0x7F03FE`.
- `0xE7`: raw screen X/Y bytes.
- `0xF4`: constructor emits canonical 0/1; only those stored values receive a boolean editor.
- `0xEB`: live Sound menu + table agree on `[duration/speed-of-change, volume]`; upstream documents `0xFF` as normal volume.
- `0x29`: constructor stores `index | 0x80`; only canonical high-bit-set encodings receive the logical 0–127 editor.
- `0x82`: one raw NPC ID byte.
- `0xC8`: one raw Special Dialog ID byte; arbitrary raw values are not reinterpreted as rename/switch-PC actions.
- Existing base-editor families also cover item/category forms, text/message IDs, item/gold checks, party controls, `0x83` enemy load, palette/storyline/raw solidity, movement speed/position, direct facing, animation/timing, location, battle flags and other proven fixed-width operands.

Ordinary script-memory UI addresses are even `0x7F0200–0x7F03FE` and round-trip to one-byte `/2` slots. Odd/out-of-range values fail closed. PC-only extended-memory raw slots and bank-7F offset forms are separate models and are not silently translated into that address space.

Doubled targets also fail closed on odd stored bytes. The generic one-byte doubled representation allows logical 0–127 unless a stricter live constructor/menu domain is independently established.

Relative jump writes have one additional invariant: when the jump byte changes, the new target must be a decoded command boundary or function end. Existing malformed jumps may be preserved when another operand changes. This applies to ordinary comparisons and PC-only `0x6E` alike.

### Dynamic / mode-dependent PC boundaries

`0xEC` All Purpose Sound uses live Sound-menu constructors to establish exact known forms:

- `88/F0/F2`: 1 argument byte total.
- `14/19`: 2 argument bytes total.
- `82/83/85/86`: 3 argument bytes total.

Known forms receive read-only semantics. Unknown/truncated forms fail closed. EC remains unwritable.

For `0x2E`, `0x88` and `0x4E`, the platform-specific PC parser is the authoritative boundary source when generic menus suggest a different construction:

- `0x2E` Color Math: PC modes 4/5 = five argument bytes; PC mode 8 = three.
- `0x88` Multi-mode Copy: PC modes 0/2/3/4/5/8 = 1/3/3/4/4/2 argument bytes.
- `0x4E` Memory Copy: PC parser layout is `[destination u16, encodedLength u16, payload]`, where the encoded length includes the two-byte length field itself.

These opcode families remain read-only through the fixed-width argument writer even when a particular mode has a known boundary.

`0xFF` Mode 7 uses live Mode7Menu + PC parser evidence for read-only boundaries/semantics: scenes `00–89` are one argument byte, `90` and `97` carry three additional raw parameters, and `91–96/98` are one-byte special forms. Unknown `8A–8F` and `99–FF` modes fail closed.

`0xF1` Color Addition remains **boundary-unresolved**. The PC parser/table interprets a nonzero first byte as a two-argument form, while the live ColorAdd menu can construct a nonzero one-argument form. Raw bytes can therefore be ambiguous with the next opcode. Lexeditor stops disassembly at F1 rather than choosing one interpretation.

### Intentionally excluded from named editing

- `0x48–0x4D`: PC overrides replace the SNES address with a two-byte **segment address**; current menus do not establish a reversible full PC RAM address mapping.
- `0x60`: PC width override conflicts with the generic 16-bit-immediate constructor semantics.
- `0x61`: upstream literally describes the operation width as `1 byte?`.
- `0x67`: constructor/table disagree on reset-mask polarity (`reset bitmask` vs `bits to keep`).
- `0x75/0x76`: upstream says set memory to `1 (0xFF?)`; `0x77` says `1 byte?`.
- `0x7B`: unused NPC jump with unknown destination fields and `speed/height?` operands.
- `0x27/0x28`: live menus treat the displayed object ID as the stored argument while helper constructors divide the supplied ID by two.
- `0x8D`: upstream itself notes pixel-position/shift mismatch.
- `0x8E`: live menu marks bit 6 and bits 2–3 unknown and does not establish a complete reversible priority interpretation.
- `0x92/0x9C`: constructor doubles magnitude while live menu decode displays the stored magnitude directly.
- `0x9E/0x9F`: table definitions and constructors remain internally inconsistent; Lexeditor records their PC widths unresolved.
- `0xE4/0xE5/0xE6`: unresolved tile-copy/layer-scroll flags or fields.
- `0xEC`: dynamic known-form reads only; no subcommand writer yet.
- `0xF1`: unresolved command boundary.
- `0xFF`: Mode 7 forms remain semantic-only/read-only.
- Other variable/unresolved commands remain read-only unless a relocation-capable assembler and stronger PC evidence are developed.

## Scene maps / tiles / palettes

**Status: proven isolated PC raster paths; composition incomplete.**

CTViewer establishes the current-PC isolated resource paths used by Lexeditor:

- L1/L2: `BGSetTable` -> `map_bin/cg*.bin` -> PC 3-byte `ChipTable_*.dat` corners -> BGR555 palette -> MapTable tile IDs.
- L3: `weather_bin/cg*.bin` -> scene-indexed `ChipTableBg3_*.dat` -> 256 four-corner PC tiles -> 4-color palette groups -> MapTable L3.
- Scene/world palettes are fixed 256-color BGR555 resources; Lexeditor preserves headers/trailing bytes.

MapTable main/sub/effect bits are surfaced using CTViewer's PC labels, but no full blend/priority runtime is claimed. CTViewer's current `maps.rs` reads four PC `PrioMap` bytes and explicitly calls them **unknown layer priority data** that “might” relate to PC rendering/SNES emulation. Lexeditor therefore keeps them raw and composition disabled.

## BGAnime chip animations

**Status: structural PC descriptor decoder only; playback disabled.**

CTViewer establishes the leading animation count, frame count, four-chip source/destination groups, PC offset `/32`, and duration upper-nibble mapping (`0x10/0x20/0x40/0x80` -> 16/12/8/4 ticks). The lower duration nibble is unknown.

CTViewer's renderer initialization/advance sequence is renderer behavior, not proof of Steam runtime phase. Lexeditor does not enable playback until the actual game's initial copy/frame behavior is independently established.

## Gameplay stats: enemies / items / techs / shops

**Status: candidate families only; no structured writer.**

ChronoMod proves archive extraction/replacement, not gameplay records. CTExt proves loose-file/CTP loading, not enemy/item/tech layouts. Historical mods do not establish current Steam record boundaries, and SNES/DS tables are not assumed to transfer.

`tools/chrono_trigger_inventory.py` uses ARC1 index metadata and optional four-byte declared-size peeking. `tools/chrono_trigger_probe.py` requires one explicit candidate family/path cluster, enforces compressed/declared-size caps before inflation, and reports only structural hashes/prefixes/constant-vs-variable positions. Neither assigns field meaning or writes gameplay data.

A gameplay-stat writer requires independent known-value correlation across multiple entities plus reversible CTExt loose-file validation.

## Practical next evidence needed

1. Run inventory/probe against a current Steam `resources.bin` and isolate repeated enemy/item/tech/shop families.
2. Correlate candidate fields across multiple known entities and validate reversibly before exposing a writer.
3. Independently resolve `PrioMap` and main/sub composition ordering before composed rendering.
4. Establish real-game BGAnime initial phase/frame behavior before playback.
