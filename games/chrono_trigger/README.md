# Chrono Trigger (Steam)

Lexeditor integration for the Windows Steam release (App ID `613830`). PC formats are required before a structure becomes writable; SNES offsets are never assumed to map directly to Steam.

## Safety

`resources.bin` is an immutable Vanilla source. Writes go to archive-relative CTExt project overlays with stale-hash checks where shared/fixed binary data is edited. Lexeditor does not resize Atel scripts, install CTExt DLLs, delete direct `mods/` source projects, or claim unverified Steam gameplay-stat layouts.

## Implemented

- ARC1 decoding/search/classification and bounded resource previews.
- Localization/message editing.
- Scene headers, existing exits and treasure editing.
- Scene MapTable/collision inspection plus read-only PC render diagnostics.
  - MapTable main/sub-screen target bits and effect bits are decoded using CTViewer's PC labels, but are not used to claim full composition behavior.
  - PC `PrioMap` bytes are displayed raw; their semantics remain explicitly unknown.
  - Scene-referenced `Game/field/BGAnime/bganimeinfo_*.dat` records are decoded read-only: declared animation count, four-chip destination/source ranges, source/destination offset `/32`, and frame duration upper-nibble values (`0x10/0x20/0x40/0x80` = 16/12/8/4 ticks). Unknown duration nibbles and the lower nibble are preserved rather than guessed.
  - Animation runtime phase and initial-frame behavior are not inferred, so Lexeditor does not claim animation playback yet. CTViewer's current renderer initializes animation state at frame 0/timer 0 without initially copying frame 0 into the destination chips, then advances before its first copy; that is treated as renderer behavior, not proof of Steam runtime semantics.
- Atel parsing, PC disassembly, semantics and control-flow diagnostics, with named fixed-width argument editing in both the desktop Events UI and CLI. Unsupported, variable-width and unresolved commands remain read-only.
  - Proven Steam item-command editors include `0xC7` Add Item from Memory, `0xCA` Add Item, `0xCB` Remove Item, `0xD5` Equip Item and `0xD7` Get Item Quantity.
  - Their PC-only extra category byte is exposed as a raw numeric value rather than an invented enum/global item ID. C7/D7 local-memory slots are shown as even `0x7F0200`–`0x7F03FE` script-memory addresses and round-trip back to the one-byte PC slot without resizing commands.
  - Proven conditionals include `0x18` Check Storyline; current/since-last button/action checks `0x2D`, `0x30`/`0x31`, `0x34`–`0x39`, `0x3B`/`0x3C`, `0x3F`–`0x44`; and PC script-memory comparisons `0x12`–`0x15`.
  - `0x12`/`0x13` compare one `/2` script-memory slot against an immediate u8/u16 value; `0x14`/`0x15` compare two `/2` script-memory slots at 8/16-bit width. Comparator values 0–7 are the proven equality/order/bitwise operations and the final byte is the jump-if-false distance. `0x16` remains excluded because its bank-7F/operator packing is a distinct unresolved layout.
  - Changing a relative jump byte is allowed only when the new target lands on a decoded command boundary. Existing malformed jump bytes are preserved and do not block unrelated fixed-width operand edits when the jump itself is unchanged.
  - Script-memory assignment/math controls include `0x19`, `0x1A`, `0x4F`/`0x50`, `0x51`/`0x52`, `0x5B`, `0x5D`/`0x5E`, `0x5F`, and `0x71`/`0x72`/`0x73`; all use the same validated even `0x7F0200`–`0x7F03FE` `/2` address model.
  - Proven local bit controls are `0x63` Set Bit, `0x64` Reset Bit, `0x69` Set Bits, `0x6B` Toggle Bits and `0x6F` Shift Right. Bit indices/shifts are limited to 0–7; `0x67` remains excluded because upstream's constructor/table descriptions disagree on its mask semantics, and bank-7F `0x65`/`0x66` remain separate/unclaimed.
  - PC-only extended-memory editors cover `0x3A`, `0x3D`, `0x3E`, `0x45`, `0x46`, `0x70`, `0x74` and `0x78`. Their local/extended/party operands are deliberately exposed as **raw one-byte slots**, because Temporal Redux's PC factories take those raw bytes directly rather than passing them through the ordinary `0x7F0200` `/2` address helper. `0x6E` stays read-only despite a known PC width because its extended-memory comparison semantics/address model are not established strongly enough.
  - Function-call editors `0x02`–`0x07` decode an even doubled target byte plus packed priority/function nibbles. Object/PC target IDs are exposed as `storedByte/2`, function and priority are 0–15, and the opcode itself fixes continue/sync/halt mode. Odd stored target bytes remain read-only.
  - Proven object controls `0x0A`, `0x7C`, `0x7D` likewise decode only even `objectId*2` target bytes; processing neighbors `0x0B`/`0x0C` are not assumed to share that encoding.
  - Constructor-evidenced property editors `0x0D`/`0x0E` expose only the known low two bits (`through walls`, `through PCs`, `onto tile`, `onto object`). Every unknown high flag bit is preserved exactly during writes and is shown as unknown in semantics rather than cleared or named.
  - Additional movement/follow editors include `0x8F`, `0x94`/`0x95`, `0x96`/`0x97`, `0x98`/`0x99`, `0x9A`, `0xA0`/`0xA1`, and looping `0xB5`/`0xB6`. Where upstream establishes only raw X/Y bytes, Lexeditor labels them as coordinate bytes rather than inventing tile/pixel units. `0x9E`/`0x9F` remain excluded because upstream width metadata is internally inconsistent and Lexeditor marks those widths unresolved.
  - Party/screen/location-from-memory controls include `0xD9` six raw party coordinate bytes, `0xE2` four validated `/2` script-memory source addresses (location/X/Y/facing), `0xE7` raw screen-scroll X/Y bytes and canonical `0xF4` screen-shake boolean values 0/1. Noncanonical shake bytes remain read-only.
  - Audio now includes proven `0xEB` Song Volume as `[duration, volume]`, with `0xFF` documented upstream as normal volume. `0xEC` is **not writable**: its live Sound menu proves subcommand-dependent widths, so Lexeditor now decodes known EC forms dynamically (1/2/3 argument bytes) and stops fail-closed on unknown subcommands instead of assuming a fixed three-byte payload.
  - Compact one-byte editors include `0x29` Load ASCII (only canonical stored bytes with the high bit set; UI exposes logical index 0–127 and rewrites `index | 0x80`), `0x82` raw NPC ID and `0xC8` raw Special Dialog ID.
  - Existing proven fixed-width controls also include script-memory outputs `0x20`/`0x55`/`0x7F`, coordinate reads `0x21`/`0x22`, palette `0x33`, storyline `0x5A`, LoadEnemy/solidity `0x83`/`0x84`, Script/NPC movement `0x87`/`0x89`/`0x8A`/`0x8B`/`0x8C`, facing `0xA6`/`0xA7`, animation IDs `0xAA`/`0xAB`/`0xAC`/`0xB7`, pause ticks `0xAD`, message-table selection `0xB8`, Explore Mode `0xE3`, sound/music IDs and raw darken duration `0xF0`.
  - `0x84` is deliberately exposed only as a raw solidity-properties byte; its bit assignments are not invented.
  - `0x21`/`0x22` decode the documented doubled target byte only when it is even; malformed odd encodings remain read-only. Direct facing is editable only for documented values 0–3.
  - Ambiguous commands stay out of the named editor layer: current evidence is insufficient for `0x8D` pixel-position shift behavior, `0x8E` priority flags, `0x27`/`0x28` target encoding, `0x16` bank-7F comparison packing, PC-only `0x6E` extended-memory comparison semantics, `0x67` reset-mask polarity, `0x61` operation width (upstream literally labels it `1 byte?`), `0x9E`/`0x9F` movement widths/targets, and variable-width `0xEC` writes.
- Eight overworld headers plus existing world exits/triggers/script-address editing.
- Fail-closed read-only world script disassembly.
- Localized labels where Steam message resources exist.
- Actual PC scene/world PNG raster rendering in both the desktop Map views and `tools/chrono_trigger_map.py`.
  - Scene Map can switch between structural collision/tile-ID views and isolated rendered L1/L2/L3.
  - Scene L3 follows CTViewer's current PC path: `weather_bin/cg*.bin`, scene-indexed `ChipTableBg3_*.dat`, 256 four-corner tiles, PC 3-byte corner records, and 4-color palette groups.
  - Worlds has a Map tab for isolated rendered L1/L2 only.
  - Animated L1/L2 chip playback and main/sub-screen blend/priority composition remain explicitly unsupported.
- Fixed 256-color BGR555 scene/world palette editing.
- Project change inventory/revert and deterministic CTP export.
- CTExt audit/deploy/deactivate/manifest-owned undeploy.
- Full-scene integrity audit and Atel jump-boundary diagnostics.
- Gameplay-data research tooling that remains read-only:
  - `chrono_trigger_inventory.py` ranks battle/enemy/tech/item/shop/party candidates from the real ARC1 index, clusters parent directories/extensions/stored sizes, can optionally peek only each candidate's decoded 4-byte declared payload size, and emits repeated path/size groups suitable for follow-up probing.
  - `chrono_trigger_probe.py` decompresses only an explicitly selected family (optionally one path prefix), with hard resource/stored/uncompressed-size caps checked first, then reports hashes, bounded prefix hex, payload-size clusters, and byte-level constant/variable positions across same-size samples. Those differences are structural evidence only; no stat meaning is assigned.

## Tools

- `tools/chrono_trigger_project.py` — changes/revert/CTP
- `tools/chrono_trigger_ctext.py` — status/audit/deploy/deactivate/undeploy
- `tools/chrono_trigger_event.py` — show/set-args/set-fields
- `tools/chrono_trigger_palette.py` — palette show/set
- `tools/chrono_trigger_map.py` — scene L1/L2/L3 and world L1/L2 PNG render
- `tools/chrono_trigger_inventory.py` — real-install resource-family inventory + optional 4-byte declared-size clustering
- `tools/chrono_trigger_probe.py` — bounded read-only payload comparison for one candidate family/path cluster

## Validation

- Dedicated `Chrono Trigger checks` workflow compiles the plugin/tools, validates the descriptor, auto-discovers all `test_chrono_trigger_*.py` suites, runs the managed ARC1/CTExt smoke, checks editor JavaScript, and runs Playwright desktop regressions.
- Event-editor regressions cover PC item/category layouts, script-memory `/2` address round-trips, doubled target IDs, function-call priority/function packing, local bit masks/shifts, raw-slot PC-only extended-memory operations, known property-bit writes with unknown-bit preservation, E2 location-from-memory addresses, party/screen controls, raw-coordinate movement/follow commands, EB song volume, canonical ASCII index encoding, raw NPC/dialog operands, palette/storyline/raw-solidity, movement/facing/animation/pause controls, storyline/button conditionals, 8/16-bit immediate and memory-to-memory comparisons, safe relative-jump retargeting, fixed-size preservation, partial edits, and fail-closed invalid encodings.
- Disassembly regressions now cover every live Sound-menu EC width class: subcommands `88/F0/F2` = one argument byte, `14/19` = two, and `82/83/85/86` = three; unknown/truncated EC forms fail closed and EB remains fixed at two argument bytes.
- Research-tool regressions enforce family/path scoping, deterministic cluster output, pre-decompression size caps, no-decompression inventory mode, 4-byte-only declared-size peeking, and same-size byte-difference reporting.
- Playwright covers scene/world raster views and render diagnostics plus real Events UI writes: the main regression edits `NPC Facing` and a `0x13` 16-bit comparison with stale-SHA rollover, while a dedicated bit-editor regression edits `0x6B` Toggle Bits from mask/address values to exact refreshed bytes `AA 20`.

## Evidence

See [`FORMAT_EVIDENCE.md`](FORMAT_EVIDENCE.md) for the PC-format evidence ledger and explicit proven/read-only/unresolved boundaries.

- ChronoMod: <https://github.com/jimzrt/ChronoMod> — ARC1 container/replacement evidence, not gameplay-stat layouts.
- CTViewer: <https://github.com/GitExl/CTViewer>
- Temporal Redux: <https://github.com/OnemusCT/temporal-redux>
- CTExt: <https://github.com/TheRealBiggs/ctext>

## Remaining high-value work

1. Determine exact current-PC initial-frame/phase behavior for scene chip animations before enabling playback, and independently evidence main/sub-screen composition and `PrioMap` semantics before implementing composed rendering.
2. Run the inventory/probe pipeline against a current real Steam install, isolate repeated battle/enemy/item/tech record families, and reverse-engineer fields only after cross-record correlations and reversible loose-file tests establish them.
3. Keep improving event editing without moving command boundaries unless a tested assembler/relocation model is developed; keep ambiguous address/operator/target encodings read-only.
4. Keep expanding browser-level regression coverage for integrated Chrono desktop surfaces.
5. Keep ARC1 rebuilding as fallback experimentation only after real-install round-trip validation; CTExt loose/CTP stays the default deployment model.
