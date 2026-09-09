# Chrono Trigger Steam format evidence ledger

This file records why Lexeditor treats a Steam structure as writable, read-only, or unresolved. The goal is to stop future work from quietly substituting SNES assumptions or another tool's renderer behaviour for actual PC-format evidence.

## Evidence classes

- **Proven PC layout** — a current-PC parser/constructor, multiple independent fixtures, or a round-trip test establishes byte boundaries and operand meaning. Fixed-width writes may be enabled if invariants are covered.
- **Structural PC evidence** — boundaries/fields can be decoded, but runtime semantics or write behaviour are not established. Read-only inspection only.
- **Renderer behaviour only** — another viewer implements something, but there is no evidence the Steam runtime behaves identically. Do not promote this to game semantics.
- **Candidate only** — filename/path/keyword evidence without a verified record layout. Do not build a structured editor.

## ARC1 `resources.bin`

**Status: proven container layout; Vanilla remains immutable in Lexeditor.**

ChronoMod's `resourcebin.cpp` independently establishes the ARC1 header/index model, XOR stream keyed by file offset, gzip-wrapped entries, extraction, and archive rebuilding. Lexeditor uses an independent reader and deliberately keeps installed `resources.bin` read-only; normal writes are CTExt loose-file/CTP overrides.

Important limitation: ChronoMod treats archive entries as opaque replacement blobs. Its UI/source contains no enemy/item/tech/battle record parser. It is therefore evidence for the **container**, not for gameplay-stat structures.

Each ARC1 resource block also has a decoded four-byte big-endian uncompressed-size prefix before its gzip stream. Lexeditor can read that prefix independently with `ResourceArchive.declared_payload_size()` without inflating the resource. This is valid size metadata, not gameplay-field evidence.

## Field events (`Game/field/atel/Atel_*.dat`)

**Status: PC structural parser + growing proven fixed-width operand set.**

Temporal Redux has explicit `Platform.PC` command-width overrides, command-table descriptions and constructors/menu models. Lexeditor only exposes named writes where the PC command width and operand meaning are explicit and the existing command can be rewritten without moving boundaries.

Current notable PC-specific layouts include:

- `0x12` immediate 8-bit comparison — script-memory `/2` slot, u8 value, operation 0–7, forward jump byte when false.
- `0x13` immediate 16-bit comparison — script-memory `/2` slot, little-endian u16 value, operation 0–7, forward jump byte when false.
- `0x14`/`0x15` memory-to-memory comparison — two script-memory `/2` slots, operation 0–7, forward jump byte when false; opcode selects 8/16-bit width.
- `0x18` Check Storyline — storyline threshold + forward jump byte.
- Button/action checks `0x2D`, `0x30`/`0x31`, `0x34`–`0x39`, `0x3B`/`0x3C`, `0x3F`–`0x44` — check/mode is encoded in the immutable opcode; the sole argument is the number of bytes to jump if the check fails.
- `0x02`–`0x07` function calls — one doubled object/PC target byte plus one packed `priority<<4 | functionId` byte. The opcode itself fixes continue/sync/halt mode. Lexeditor exposes the logical target only when the stored target byte is even.
- `0x0A`, `0x0B`, `0x0C`, `0x7C`, `0x7D` object controls — live constructors/menus store `objectId*2`; odd stored targets remain read-only. For `0x0B`/`0x0C`, the opcode itself fixes processing off/on and Lexeditor edits only the target byte.
- `0x0D`/`0x0E` movement/destination properties — constructors define only bits 0–1 (`through walls`, `through PCs`, `onto tile`, `onto object`). Lexeditor rewrites only those known bits and preserves every higher unknown bit exactly.
- `0x19` Get Result to script memory — one `/2` script-memory result slot.
- `0x1C` Get Result to bank 7F — live `GetResultMenu` decodes the one stored byte as `0x7F0000 + byte`. Because only one byte is encoded, Lexeditor deliberately narrows the writable UI range to `0x7F0000`–`0x7F00FF`; it does not inherit the menu's broader visual address bound.
- `0x1A`, `0x4F`/`0x50`, `0x51`/`0x52`, `0x5B`, `0x5D`/`0x5E`, `0x5F`, `0x71`/`0x72`/`0x73` — explicit local script-memory result/check/store/copy/add/subtract/increment/decrement layouts.
- `0x23`/`0x24` Get Facing — live `GetFacingMenu` fixes object vs PC by opcode and writes `targetId*2` plus one `/2` script-memory result destination. Odd target bytes remain read-only.
- `0xA8`/`0xA9` Face Object/PC — live `FaceObjectMenu` fixes target type by opcode and writes `targetId*2`. Odd stored target bytes remain read-only.
- `0x63`/`0x64` Set/Reset Bit — bit index 0–7 plus `/2` script-memory slot.
- `0x69` Set Bits and `0x6B` Toggle Bits — raw u8 bitmask plus `/2` script-memory slot.
- `0x6F` Shift Bits — right-shift count 0–7 plus `/2` script-memory slot.
- PC-only `0x3A`, `0x3D`, `0x3E`, `0x45`, `0x46`, `0x70`, `0x74`, `0x78` — explicit PC factories + PC width overrides establish two one-byte operands. These are exposed as **raw local/extended/party slot bytes** because the PC factories take those bytes directly instead of using the ordinary `get_offset(0x7F0200...)` helper. Lexeditor does not fabricate an address mapping for them.
- `0x8F`, `0x94`/`0x95`, `0x96`/`0x97`, `0x98`/`0x99`, `0x9A`, `0xA0`/`0xA1`, `0xB5`/`0xB6` — follow/move constructors whose operand order matches the command table. Direct X/Y operands are exposed as **coordinate bytes**, not as tile/pixel units, because those units are not independently established for these opcodes.
- `0x9D` Vector Move from Memory — live `VectorMoveFromMemMenu` writes two ordinary `/2` script-memory source slots, one for direction and one for magnitude, and decodes them with the inverse mapping.
- `0xD9` Move Party — six raw coordinate bytes (PC1 X/Y, PC2 X/Y, PC3 Y/X as laid out by the command table; Lexeditor preserves the literal byte order rather than adding unit claims).
- `0xE2` Change Location from Memory — four one-byte `/2` script-memory offsets for location, X, Y and facing. Lexeditor uses the same validated even `0x7F0200–0x7F03FE` address model instead of accepting the menu's inclusive `0x7F0400` UI bound, which cannot fit in one encoded slot byte.
- `0xE7` Scroll Screen — raw X/Y coordinate bytes.
- `0xF4` Shake Screen — constructor writes canonical 0/1; Lexeditor exposes a boolean only for those stored values and leaves noncanonical nonzero bytes read-only.
- `0xEB` Song Volume — live Sound menu and command table agree on `[duration/speed-of-change, volume]`, both u8; upstream documents `0xFF` as normal volume.
- `0x29` Load ASCII — constructor stores `index | 0x80`; Lexeditor exposes logical index 0–127 only when the stored high bit is present and always re-encodes that high bit.
- `0x82` Load NPC — one raw NPC ID byte.
- `0xC8` Special Dialog — one raw dialog ID byte; rename/switch-PC meanings are not inferred from arbitrary values in this raw editor.
- `0x83` Load Enemy — enemy ID is PC u16 + slot/static byte.
- `0xC9` Check Inventory — PC item ID is u16 + jump byte.
- `0xC7` Add Item from Memory — local-memory slot + raw category.
- `0xCA`/`0xCB` Add/Remove Item — item index + raw category.
- `0xD5` Equip Item — PC ID + item index + raw category.
- `0xD7` Get Item Quantity — item index + raw category + local-memory destination.
- `0xDC`–`0xE1` Change Location — PC layout is u16 scene + separate facing/X/Y bytes.
- `0x21`/`0x22` coordinate reads — doubled target byte + X/Y local-memory destinations. Lexeditor decodes only even target bytes.
- `0x20`/`0x55`/`0x7F` local-memory outputs and `0x8A`/`0x8C`/`0xA7` local-memory sources use the proven `/2` script-memory encoding.
- `0x33` palette ID, `0x5A` storyline value, `0x84` raw solidity-properties byte, `0x87` script speed, `0x89` NPC speed, `0x8B` tile position, `0xA6` facing, `0xAA`/`0xAB`/`0xAC`/`0xB7` animation IDs/count and `0xAD` pause ticks are fixed-width explicit operands.

Comparison operation values come directly from Temporal Redux's command model: 0 equals, 1 not-equals, 2 greater-than, 3 less-than, 4 greater-or-equal, 5 less-or-equal, 6 bitwise-AND-nonzero and 7 bitwise-OR-nonzero. Invalid stored operation bytes fail closed rather than being normalized.

All ordinary local script-memory UI addresses are even `0x7F0200`–`0x7F03FE` and round-trip to the one-byte `/2` slot. Invalid/odd values fail closed. PC-only extended-memory factories are a separate raw-slot family and are not silently translated through that address model. `0x1C` is also separate: its one operand is a literal byte offset from `0x7F0000`, not a `/2` script-memory slot.

For doubled object/PC target encodings, Lexeditor likewise fails closed on odd stored bytes rather than rounding. Logical target IDs are limited by the one-byte doubled representation (`0–127`) unless a stricter constructor range is independently explicit (for example follow-PC commands that document `1–6`).

Relative jump writes have an additional invariant: if the jump byte itself changes, the proposed target must be one of the decoded command boundaries (or function end). An unchanged pre-existing invalid jump does not block changing another fixed-width operand. This avoids silently creating new mid-command control-flow edges while preserving unusual existing data.

### `0xEC` all-purpose sound width

**Status: proven dynamic PC command boundaries; read-only semantics/writes.**

Temporal Redux's live `SoundMenu.py` contradicts a single fixed-width interpretation of `0xEC`. Its constructors emit:

- subcommands `0x88`, `0xF0`, `0xF2`: subcommand byte only → **1 argument byte** total.
- subcommands `0x14`, `0x19`: subcommand + one parameter → **2 argument bytes** total.
- subcommands `0x82`, `0x83`, `0x85`, `0x86`: subcommand + two parameters → **3 argument bytes** total.

Lexeditor therefore treats `0xEC` as dynamic during PC disassembly. Known forms receive read-only semantic labels using those exact live-menu operations/parameters. Unknown subcommands fail closed and truncated known forms do not consume bytes from the following command. No named EC writer is exposed yet; establishing boundaries and labels does not imply every subcommand's runtime behavior is ready to edit.

Still intentionally excluded from named editing:

- `0x16` comparison: bank-7F addressing/operator packing is a distinct layout and is not normalized from the plain script-memory comparison model.
- `0x60`: PC override differs from the generic constructor's 16-bit immediate form; do not normalize until PC operation semantics are independently settled.
- `0x61`: the upstream command table literally describes the operation as local-memory subtraction **`(1 byte?)`**, so Lexeditor does not turn that uncertainty into a width/semantic claim.
- `0x65`/`0x66` bank-7F bit commands: their address/bit packing differs from the plain script-memory bit commands.
- `0x67` Reset Bits: Temporal Redux's constructor names the operand a reset bitmask while the command table describes it as “bits to keep”; Lexeditor does not choose a polarity without better evidence.
- `0x6E` PC-only extended-memory comparison: width/factory order are known, but public extended-memory comparison semantics/address meaning are not strong enough yet for a named editor.
- `0x27`/`0x28`: their live menus treat the displayed object ID as the stored argument, while the helper constructors divide the supplied ID by two. That internal inconsistency is not normalized away.
- `0x8D` pixel-position: upstream code itself notes coordinate/shift mismatch.
- `0x8E` sprite priority: the live menu names bit 6 and bits 2–3 as unknown flags, and the fetched apply path does not establish a complete reversible interpretation of the priority byte.
- `0x92`/`0x9C` direct vector movement: the constructor doubles magnitude, while the live menu's apply path displays the stored magnitude byte directly without undoing that transform. Lexeditor does not pick one interpretation.
- `0x9E`/`0x9F`: Temporal Redux's table definitions are internally inconsistent with their constructors; Lexeditor therefore records these PC widths as unresolved (`-1`) and does not expose editors.
- `0xE4`/`0xE5`/`0xE6`: tile-copy/scroll-layer behavior includes unresolved flags or unknown fields, so these remain read-only despite fixed byte counts.
- `0xEC`: dynamic boundaries and known read-only semantics are decoded, but named subcommand writes remain out until each desired subcommand's runtime semantics are promoted independently.
- variable/dynamic or unresolved widths generally remain read-only until a relocation-capable assembler exists.

## Scene maps / tiles / palettes

**Status: proven isolated PC raster paths; composition remains incomplete.**

CTViewer provides current-PC paths/layouts used by Lexeditor for isolated rendering:

- L1/L2: `BGSetTable` -> packed `map_bin/cg*.bin` -> PC 3-byte `ChipTable_*.dat` corners -> BGR555 palette -> MapTable tile IDs.
- L3: `weather_bin/cg*.bin` -> scene-indexed `ChipTableBg3_*.dat` -> 256 four-corner PC tiles -> 4-colour palette groups -> MapTable L3.
- Scene/world palettes are fixed 256-colour BGR555 resources with preserved header/trailing bytes in Lexeditor's writer.

MapTable main/sub/effect bits are surfaced using CTViewer's PC labels, but Lexeditor does not currently use those labels to claim a complete blend/priority renderer. CTViewer's current `maps.rs` reads exactly four bytes from the PC `PrioMap` file and explicitly comments that they are **unknown layer priority data** which “might” relate to the PC renderer/SNES emulation. That is structural evidence for the bytes, not proof of Steam runtime ordering, so Lexeditor keeps `PrioMap` raw and composition disabled.

## BGAnime chip animations

**Status: structural PC descriptor decoder only; playback disabled.**

CTViewer establishes the descriptor shape:

- PC leading animation count.
- frame count per animation.
- four-chip destination/source groups.
- PC chip offsets divide by 32.
- duration is encoded in the upper nibble: `0x10/0x20/0x40/0x80` => 16/12/8/4 ticks.
- lower duration nibble is unknown.

Do **not** infer the Steam runtime's starting frame/phase from CTViewer. Its current renderer initializes `frame=0`, `timer=0`, leaves the animated source bitmap separate at load, and on expiry increments the frame before copying chips to the destination. No animation-specific commit history was found explaining that as verified game behaviour. Lexeditor therefore exposes descriptor diagnostics but no playback.

## Gameplay stats: enemies / items / techs / shops

**Status: candidate families only; no structured writer.**

Current public evidence is insufficient for a current-Steam record layout:

- ChronoMod can extract/replace arbitrary ARC1 files, but has no gameplay-record parser.
- CTExt currently provides loose-file/CTP loading and runtime hooks, but repository searches have not yielded enemy/item/tech data structures or resource decoders suitable for a stat editor.
- Historical Steam mods prove names/resources can be replaced through CT_Explore patches, but that does not establish current enemy-stat record boundaries.
- SNES/DS tables are not assumed to map to the PC port.

### Research tooling boundary

`tools/chrono_trigger_inventory.py` is the first pass. By default it uses ARC1 index metadata only: candidate path scores, parent-directory clusters, extensions and stored sizes. `--peek-sizes` additionally reads only the four-byte declared payload-size prefixes. It still does **not** decompress candidate gzip payloads. Repeated path/size groups are emitted as `probeClusters` to suggest bounded follow-up targets; equal directory/size does not prove equal record semantics.

`tools/chrono_trigger_probe.py` is the second pass. It requires one explicit candidate family and may be restricted to one archive path prefix. It enforces maximum resource count, compressed-block size and declared-uncompressed size **before** candidate decompression. For loaded samples it reports payload hashes, bounded prefix bytes, payload-size clusters, and constant/variable byte positions only among equal-size payloads. These are reverse-engineering diagnostics, not stat-field claims, and the probe has no write path.

A gameplay-stat editor should not be added merely because a byte position varies. A field needs independent semantic evidence: known-value correlation across multiple entities plus reversible loose-file validation without collateral changes.

## Practical next evidence needed

1. Run `tools/chrono_trigger_inventory.py --peek-sizes` against a current Steam `resources.bin`, preferably one family at a time, and retain promising `probeClusters` for enemy/item/tech/shop families.
2. Run `tools/chrono_trigger_probe.py` only against a selected family/path cluster. Look for repeated payload sizes, stable headers, sparse variable positions, count/pointer patterns and correlations with known game values.
3. Validate any proposed field against at least two known entities and a reversible CTExt loose-file test before exposing a writer.
4. For scene composition, independently resolve `PrioMap` and main/sub blend ordering before adding a composed renderer.
5. For BGAnime, establish the real game's initial copy/frame phase before enabling animated map playback.
