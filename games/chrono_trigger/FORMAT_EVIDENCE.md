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

## Field events (`Game/field/atel/Atel_*.dat`)

**Status: PC structural parser + growing proven fixed-width operand set.**

Temporal Redux has explicit `Platform.PC` command-width overrides and command constructors/menu models. Lexeditor only exposes named writes where the PC command width and operand meaning are explicit and the existing command can be rewritten without moving boundaries.

Current notable PC-specific layouts include:

- `0x83` Load Enemy — enemy ID is PC u16 + slot/static byte.
- `0xC9` Check Inventory — PC item ID is u16 + jump byte.
- `0xC7` Add Item from Memory — local-memory slot + raw category.
- `0xCA`/`0xCB` Add/Remove Item — item index + raw category.
- `0xD5` Equip Item — PC ID + item index + raw category.
- `0xD7` Get Item Quantity — item index + raw category + local-memory destination.
- `0xDC`–`0xE1` Change Location — u16 scene + separate facing/X/Y bytes.
- `0x21`/`0x22` coordinate reads — doubled target byte + X/Y local-memory destinations. Lexeditor decodes only even target bytes.
- `0x20`/`0x55`/`0x7F` local-memory outputs and `0x8A`/`0x8C`/`0xA7` local-memory sources use the proven `/2` script-memory encoding.
- `0x33` palette ID, `0x5A` storyline value, `0x84` raw solidity-properties byte, `0x87` script speed, `0x89` NPC speed, `0x8B` tile position, `0xA6` facing, `0xAA`/`0xAB`/`0xAC`/`0xB7` animation IDs/count and `0xAD` pause ticks are fixed-width explicit operands.

All local script-memory UI addresses are even `0x7F0200`–`0x7F03FE` and round-trip to the one-byte PC slot. Invalid/odd values fail closed.

Still intentionally excluded from named editing:

- `0x8D` pixel-position: upstream code itself notes coordinate/shift mismatch.
- `0x8E` sprite priority: upstream description leaves non-mode bits unresolved.
- `0x27`/`0x28`: target encoding evidence is inconsistent enough that Lexeditor does not normalize it.
- variable/dynamic or unresolved widths generally remain read-only until a relocation-capable assembler exists.

## Scene maps / tiles / palettes

**Status: proven isolated PC raster paths; composition remains incomplete.**

CTViewer provides current-PC paths/layouts used by Lexeditor for isolated rendering:

- L1/L2: `BGSetTable` -> packed `map_bin/cg*.bin` -> PC 3-byte `ChipTable_*.dat` corners -> BGR555 palette -> MapTable tile IDs.
- L3: `weather_bin/cg*.bin` -> scene-indexed `ChipTableBg3_*.dat` -> 256 four-corner PC tiles -> 4-colour palette groups -> MapTable L3.
- Scene/world palettes are fixed 256-colour BGR555 resources with preserved header/trailing bytes in Lexeditor's writer.

MapTable main/sub/effect bits are surfaced using CTViewer's PC labels, but Lexeditor does not currently use those labels to claim a complete blend/priority renderer. `PrioMap` remains raw because its semantics are not independently established.

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

`tools/chrono_trigger_inventory.py` therefore remains index-only. It ranks likely path families from the user's **actual** ARC1 index without decompressing candidate payloads. A gameplay-stat editor should not be added until real current-install candidates are collected and at least one record family is independently decoded and round-trip tested.

## Practical next evidence needed

1. Run `tools/chrono_trigger_inventory.py` against a current Steam `resources.bin` and retain the candidate path/size clusters for enemy/item/tech/shop families.
2. Compare multiple records in each promising family, looking first for fixed record sizes, count headers, pointer/index tables, and known-value correlations.
3. Validate any proposed field against at least two known entities and a reversible loose-file test before exposing a writer.
4. For scene composition, independently resolve `PrioMap` and main/sub blend ordering before adding a composed renderer.
5. For BGAnime, establish the real game's initial copy/frame phase before enabling animated map playback.
