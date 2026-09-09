# Chrono Trigger (Steam)

Lexeditor integration for the Windows Steam release (App ID `613830`). PC formats are required before a structure becomes writable; SNES offsets are never assumed to map directly to Steam.

## Safety

`resources.bin` is an immutable Vanilla source. Writes go to archive-relative CTExt project overlays with stale-hash checks where shared/fixed binary data is edited. Lexeditor does not resize Atel scripts, install CTExt DLLs, delete direct `mods/` source projects, or claim unverified Steam gameplay-stat layouts.

## Implemented

- ARC1 decoding/search/classification and bounded resource previews.
- Localization/message editing.
- Scene headers, existing exits and treasure editing.
- Scene MapTable/collision inspection.
- Atel parsing, PC disassembly, semantics, control-flow diagnostics and CLI fixed-width argument editing.
- Eight overworld headers plus existing world exits/triggers/script-address editing.
- Fail-closed read-only world script disassembly.
- Localized labels where Steam message resources exist.
- Actual PC scene/world L1/L2 PNG raster exporters.
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
- `tools/chrono_trigger_map.py` — scene/world L1/L2 PNG render
- `tools/chrono_trigger_inventory.py` — real-install resource-family inventory

## Evidence

- ChronoMod: <https://github.com/jimzrt/ChronoMod>
- CTViewer: <https://github.com/GitExl/CTViewer>
- Temporal Redux: <https://github.com/OnemusCT/temporal-redux>
- CTExt: <https://github.com/TheRealBiggs/ctext>

## Remaining high-value work

1. Named fixed-width Atel controls in the desktop Events UI.
2. L3/animated-tile and correct main/sub-screen map composition.
3. Desktop raster previews using the existing renderers.
4. Run the inventory against a current real Steam install and reverse-engineer actual PC battle/enemy/item/tech stat families before implementing stat editors.
5. Keep ARC1 rebuilding as fallback experimentation only after real-install round-trip validation; CTExt loose/CTP stays the default deployment model.
