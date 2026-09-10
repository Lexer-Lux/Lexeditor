# Chrono Trigger (Steam)

Lexeditor integration for the Windows Steam release (App ID `613830`). PC formats must be evidenced before a structure becomes writable; SNES/DS offsets are never assumed to map directly to Steam.

## Safety

`resources.bin` is an immutable Vanilla source. Writes go to archive-relative CTExt project overlays. Fixed binary edits use stale-hash checks where applicable and never resize Atel scripts. Lexeditor does not install CTExt DLLs, delete direct `mods/` source projects, or claim unverified Steam gameplay-stat layouts.

## Implemented

- ARC1 decoding/search/classification and bounded resource previews.
- Localization/message editing.
- Fixed scene headers, existing exits and treasure editing.
- Scene MapTable/collision inspection plus actual isolated PC L1/L2/L3 raster rendering.
  - L1/L2: BGSetTable + `map_bin/cg*.bin` + `ChipTable_*.dat`.
  - L3: `weather_bin/cg*.bin` + scene-indexed `ChipTableBg3_*.dat`, 256 four-corner tiles, PC 3-byte corner records and 4-color palette groups.
  - MapTable main/sub/effect bits are diagnostic only. PC `PrioMap` remains raw: CTViewer still describes its four bytes as unknown PC-only layer-priority data.
  - BGAnime descriptors are decoded read-only (count, four-chip source/destination groups, `/32` offsets, duration upper nibble). Steam runtime initial phase/frame behavior is not proven, so animation playback remains disabled.
  - Main/sub blend and priority composition remain unsupported until current-PC runtime semantics are independently established.
- Eight overworld headers, existing exits/triggers/script-address editing, fail-closed world-script disassembly and isolated world L1/L2 raster rendering.
- Fixed 256-color BGR555 scene/world palette editing with header/trailing-byte preservation.
- Project change inventory/revert, deterministic CTP export, CTExt audit/deploy/deactivate/manifest-owned undeploy and deployment/integrity checks.
- Read-only gameplay-data inventory/probe tooling with strict decompression caps and no stat-field claims.

## Field events

`Atel_*.dat` support includes object/function bounds, fail-closed PC disassembly, semantic summaries, control-flow diagnostics and named **fixed-width argument editing** in both the desktop Events UI and `tools/chrono_trigger_event.py`. Opcode changes, command insertion/deletion, resizing and pointer relocation remain unsupported.

### Proven writable families

- Steam item layouts: `C7`, `CA`, `CB`, `D5`, `D7`; PC category bytes remain raw.
- Conditions: `18`; button/action checks `2D`, `30/31`, `34–39`, `3B/3C`, `3F–44`; memory comparisons `12–16`.
  - `12/13` compare one `/2` script-memory slot with an immediate u8/u16 value; `14/15` compare two `/2` script-memory slots at 8/16-bit width.
  - `16` is the separately proven bank-7F 8-bit form: `[low address byte, value, comparator|page bit, jump]`. Comparator is bits 0–2, bit 7 selects `0x7F0100–0x7F01FF`, and bits 3–6 must be clear. Lexeditor exposes the resulting address only within `0x7F0000–0x7F01FF`.
- Script-memory result/store/copy/math: `19`, `1A`, `4F`, `50`, `51`, `52`, `5B`, `5D`, `5E`, `5F`, `71`, `72`, `73`, plus existing `20`, `55`, `7F` and memory-source controls. Ordinary script-memory addresses are even `0x7F0200–0x7F03FE` and round-trip through the one-byte `/2` slot.
- Narrow bank-7F result: `1C` stores one literal byte offset from `0x7F0000`; Lexeditor exposes only the actually encodable `0x7F0000–0x7F00FF` range.
- Proven bank-7F assignments:
  - `53/54`: bank-local `0x7F0000–0x7F01FF` source -> script-memory destination, 8/16-bit.
  - `58/59`: script-memory source -> bank-local `0x7F0000–0x7F01FF` destination, 8/16-bit.
  - `56`: u8 immediate -> full u16 bank offset `0x7F0000–0x7FFFFF`.
  - Wider pre-existing `53/54/58/59` offsets remain read-only because Temporal Redux constructors select those opcodes only for `is_local_mem()` (`0x7F0000–0x7F01FF`).
- PC segment-memory `48–4D` use the Steam/PC width overrides directly:
  - `48/49`: raw u16 segment source + raw one-byte local destination slot, 8/16-bit.
  - `4A/4B`: raw u16 segment destination + immediate u8/u16 value.
  - `4C/4D`: raw u16 segment destination + raw one-byte local source slot, 8/16-bit.
  - The u16 segment is **not** presented as a full PC RAM address; semantics explicitly report `fullAddressKnown: false`. Local bytes likewise stay raw rather than inheriting the generic menu's inconsistent address conversion.
- Bit ops:
  - `63` Set Bit, `64` Reset Bit, `69` Set Bits, `6B` Toggle Bits and `6F` Shift Right use ordinary `/2` script memory.
  - Bank-7F `65/66` Set/Reset Bit use `[bitIndex|pageBit, lowAddress]`: bits 0–2 are the bit index, bit 7 selects the upper `0x100`-byte page, and undocumented bits 3–6 must be clear. The editable address domain is exactly `0x7F0000–0x7F01FF`.
- PC-only raw-slot ops: `3A`, `3D`, `3E`, `45`, `46`, `6E`, `70`, `74`, `78`. Local/extended/party operands remain raw bytes because the PC factories do not run them through the ordinary `/2` address helper.
  - `6E` is a raw-slot 8-bit comparison `[extendedSlot, value, comparator, jump]`; comparator is validated to 0–7 and the jump byte uses the same decoded-command-boundary validator as other conditionals.
- Function calls `02–07`: doubled target byte + packed priority/function nibbles; opcode fixes continue/sync/halt.
- Doubled object controls `0A`, `0B`, `0C`, `7C`, `7D`; `0B/0C` edit only the target while the opcode keeps processing off/on fixed.
- Facing target/result controls:
  - `23/24`: doubled object/PC target + `/2` script-memory facing destination.
  - `A8/A9`: doubled object/PC target.
  - `1E/1F/25/26`: NPC Up/Down/Left/Right is fixed by opcode; target is stored `NPC ID * 2` and is limited to the live menu's `0x00–0x32` domain. Larger even encodings stay read-only.
- Property flags `0D/0E`: only constructor-evidenced bits 0–1 are editable; every unknown high bit is preserved exactly.
- Movement/follow: `7A`, `8F`, `94/95`, `96/97`, `98/99`, `9A`, `9D`, `A0/A1`, `B5/B6`, plus existing `87/89/8A/8B/8C/A6/A7`.
  - `7A` exposes literal X/Y coordinate bytes plus a conservative raw `height/speed` byte.
  - `9D` uses two `/2` script-memory sources for direction and magnitude.
  - Raw X/Y operands stay labeled **coordinate bytes** unless tile/pixel units are independently evidenced.
- Party/screen/location-memory: `D9` six party coordinate bytes, `E2` four `/2` source addresses (location/X/Y/facing), `E7` screen-scroll X/Y, canonical `F4` screen-shake boolean.
- Audio: `EB` Song Volume `[duration, volume]`; upstream documents `0xFF` as normal volume.
- Compact one-byte commands: `29` Load ASCII (`index | 0x80` canonical form only), `82` raw NPC ID, `C8` raw Special Dialog ID.
- Existing base-editor families also cover text/message table, party management/checks, item/gold checks, location changes, animation/timing, battle flags, Explore Mode, palette/storyline/raw solidity, sound/music IDs and darken duration.

### PC disassembly hardening

`0xEC` All Purpose Sound is dynamically decoded from the live Temporal Redux Sound menu instead of assuming a fixed payload:

- `88/F0/F2` -> 1 argument byte total (subcommand only)
- `14/19` -> 2 argument bytes total
- `82/83/85/86` -> 3 argument bytes total

Known EC forms receive read-only semantic labels. Unknown subcommands and truncated known forms fail closed so they cannot consume the following opcode. **EC remains unwritable through both named controls and raw `set-args`.**

`0xFF` Mode 7 is also dynamic on PC. Live Mode7Menu evidence is used for **read-only semantics only**:

- scenes `00–89`: one scene byte
- specials `90` and `97`: special byte + three raw parameters
- specials `91–96` and `98`: special byte only
- unknown modes `8A–8F` and `99–FF` fail closed rather than being guessed as one-byte forms

The shared fixed-width writer still rejects `0xFF` because its PC width is dynamic. No Mode 7 writer exception was added.

`0x2E`, `0x88` and `0x4E` follow Temporal Redux's **platform-specific PC parser** when generic menus disagree:

- Color Math `2E`: PC modes 4/5 have five argument bytes; PC mode 8 has three.
- Multi-mode Copy `88`: PC modes 0/2/3/4/5/8 have 1/3/3/4/4/2 argument bytes respectively.
- Memory Copy `4E`: PC is `[destination u16, encoded-length u16, payload]`; the encoded length includes its own two-byte field.

All three opcode families remain unwritable through the fixed-width raw writer even when a particular PC form has a known boundary.

`0xF1` Color Addition is **boundary-unresolved**: the platform PC parser/table treats a nonzero first argument as a two-argument form, while the live ColorAdd menu can construct a nonzero one-argument form. Raw bytes cannot safely distinguish those interpretations, so field disassembly stops at F1 rather than consuming a possible following opcode.

### Intentionally read-only / unresolved

- `60` PC width/constructor semantic conflict; `61` operation width is literally documented upstream as `1 byte?`.
- `67` reset-mask polarity conflict.
- `75/76/77`: upstream descriptions include `1 (0xFF?)` / `1 byte?` uncertainty.
- `7B` unused NPC jump with unknown destination and `speed/height?` fields.
- `27/28` target normalization: live menus and helper constructors disagree about `/2` handling.
- `8D` pixel-position shift behavior; `8E` priority byte contains explicitly unknown flags and lacks a complete reversible menu decode.
- `92/9C` direct vector movement: constructor doubles magnitude but the live menu does not undo that on decode.
- `9E/9F` movement widths/targets: upstream metadata remains internally inconsistent and Lexeditor marks those widths unresolved.
- `E4/E5/E6` tile-copy/layer-scroll unknown flags/fields.
- `F1` command boundary due conflicting PC parser/menu evidence.
- `FF` Mode 7 writes: decoded forms remain semantic-only because the opcode is dynamically sized.
- variable/dynamic unresolved command writes generally.

## Validation

The dedicated `Chrono Trigger checks` workflow compiles plugin/tools, validates the descriptor, auto-discovers all `test_chrono_trigger_*.py` suites, runs the managed ARC1/CTExt smoke, checks editor JavaScript and runs Playwright regressions.

Regression coverage includes exact PC widths/endianness, script-memory `/2` round trips, raw PC segment u16/slot/value round trips, bank-7F page/range distinctions, `0x16` and `0x6E` comparison retargeting, doubled targets, packed call nibbles, property unknown-bit preservation, safe jump retargeting, fixed-size/partial writes, dynamic `EC` boundaries plus raw-write blocking, PC-specific `2E/88/4E` boundaries, F1 fail-closed behavior, read-only `FF` Mode 7 semantics and fail-closed malformed encodings.

Browser coverage includes:
- main scene/world/Event surfaces and a sequential NPC Facing -> `0x13` comparison save,
- `0x6B` Toggle Bits,
- PC-only extended raw-slot editing including `0x6E`,
- a three-save Events sequence for `0x23` Get Facing, `0x0B` processing target and `0x9D` vector-memory sources,
- bank-7F `0x65` + `0x16` page-bit editing,
- raw PC segment-memory `0x4B` editing with exact little-endian bytes and no full-address claim.

## Evidence

See [`FORMAT_EVIDENCE.md`](FORMAT_EVIDENCE.md) for the PC-format evidence ledger and explicit proven/read-only/unresolved boundaries.

- ChronoMod: ARC1 container/replacement evidence, not gameplay-stat layouts.
- CTViewer: current PC scene/world/map/tile/palette/render diagnostics.
- Temporal Redux: PC Atel widths, constructors, platform-specific parser and live command menus.
- CTExt: loose-file/CTP runtime loading.

## Remaining high-value work

1. Run the inventory/probe pipeline against a current Steam install and identify real gameplay-data record families before any stat editor.
2. Continue expanding only independently proven fixed-width event semantics/editors.
3. Resolve Steam BGAnime initial-frame/phase behavior and `PrioMap`/main-sub composition before playback/composed rendering.
4. Keep expanding browser-level coverage for integrated Chrono surfaces.
5. Keep ARC1 rebuilding as fallback experimentation only after real-install round-trip validation; CTExt loose files/CTP remain the default deployment model.
