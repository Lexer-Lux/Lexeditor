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
  - Additional proven fixed-width controls include script-memory outputs `0x20`/`0x55`/`0x7F`, coordinate reads `0x21`/`0x22`, Script/NPC movement controls `0x87`/`0x89`/`0x8A`/`0x8B`/`0x8C`, facing `0xA6`/`0xA7`, animation IDs `0xAA`/`0xAB`/`0xAC`/`0xB7`, pause ticks `0xAD`, message-table selection `0xB8`, Explore Mode `0xE3`, and raw darken duration `0xF0`.
  - Script-memory operands use the same validated even `0x7F0200`–`0x7F03FE` address model. `0x21`/`0x22` decode the documented doubled target byte only when it is even; malformed odd encodings remain read-only. Direct facing is editable only for documented values 0–3.
  - Ambiguous commands stay out of the named editor layer: current evidence is insufficient for `0x8D` pixel-position shift behavior, `0x8E` priority flags, and the inconsistent target encoding around `0x27`/`0x28`.
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
- ARC1 index-only gameplay-family inventory for future PC stat reverse engineering.

## Tools

- `tools/chrono_trigger_project.py` — changes/revert/CTP
- `tools/chrono_trigger_ctext.py` — status/audit/deploy/deactivate/undeploy
- `tools/chrono_trigger_event.py` — show/set-args/set-fields
- `tools/chrono_trigger_palette.py` — palette show/set
- `tools/chrono_trigger_map.py` — scene L1/L2/L3 and world L1/L2 PNG render
- `tools/chrono_trigger_inventory.py` — real-install resource-family inventory

## Validation

- Dedicated `Chrono Trigger checks` workflow compiles the plugin/tools, validates the descriptor, auto-discovers all `test_chrono_trigger_*.py` suites, runs the managed ARC1/CTExt smoke, checks editor JavaScript, and runs Playwright desktop regressions.
- Event-editor regressions cover PC item/category layouts, script-memory `/2` address round-trips, doubled coordinate-read target IDs, movement/facing/animation/pause controls, fixed-size preservation, partial edits, and fail-closed invalid encodings.
- Playwright covers scene/world raster views and render diagnostics plus the real Events UI named-editor workflow: it changes an `NPC Facing` field, verifies the `/api/save/event-fields` stale-hash POST coordinates/payload, and confirms the rerendered semantic summary and argument byte.

## Evidence

- ChronoMod: <https://github.com/jimzrt/ChronoMod>
- CTViewer: <https://github.com/GitExl/CTViewer>
- Temporal Redux: <https://github.com/OnemusCT/temporal-redux>
- CTExt: <https://github.com/TheRealBiggs/ctext>

## Remaining high-value work

1. Determine exact current-PC initial-frame/phase behavior for scene chip animations before enabling playback, and independently evidence main/sub-screen composition and `PrioMap` semantics before implementing composed rendering.
2. Run the inventory against a current real Steam install and reverse-engineer actual PC battle/enemy/item/tech stat families before implementing stat editors.
3. Keep improving event editing without moving command boundaries unless a tested assembler/relocation model is developed.
4. Keep expanding browser-level regression coverage for integrated Chrono desktop surfaces.
5. Keep ARC1 rebuilding as fallback experimentation only after real-install round-trip validation; CTExt loose/CTP stays the default deployment model.
