# Chrono Trigger (Steam)

Lexeditor integration for the Windows Steam release (App ID `613830`). The plugin is PC-format-first: SNES offsets are not promoted to Steam editors unless the corresponding PC resource layout is independently evidenced.

## Safety model

`resources.bin` is an immutable Vanilla source. Every edit is written to an archive-relative loose project path (`Game/...`, `Localize/...`) compatible with CTExt. Fixed-size shared-table writes use SHA-256 stale-write checks and preserve bytes outside documented fields.

The plugin does **not** rewrite the installed archive, resize/relocate Atel command streams, install/replace CTExt DLLs, delete direct `mods/` source projects, or invent Steam gameplay-stat layouts from SNES offsets.

## Current coverage

- ARC1 archive decoding/search/classification and bounded resource previews.
- Localization/message editing.
- Scene header, existing exit and treasure editing with fixed-size/stale-hash safety.
- Scene MapTable layout/collision inspection.
- Atel object/function parsing, PC command disassembly, semantic summaries, control-flow diagnostics, and fixed-width argument editing through the event CLI.
- Eight editable overworld headers plus existing exit/trigger/script-address editing.
- Read-only world-script disassembly for documented opcodes; unknown PC/DS commands fail closed.
- Localized scene/item/player/world labels where Steam message resources exist.
- Scene/world L1/L2 raster exporters from actual PC map/chip/palette resources.
- Scene/world 256-color BGR555 palette editing through the palette CLI.
- Project override inventory/revert and deterministic CTP export.
- CTExt audit/deploy plus reversible deactivate/manifest-owned undeploy through CLI.
- Full-scene integrity audit including referenced Atel decoding and jump-boundary diagnostics.
- Index-only real-install resource-family inventory for future Steam gameplay-stat reverse engineering.

See the Data Map and module docs/tests for exact write/read-only boundaries.

## First-party tools

- `tools/chrono_trigger_project.py` — changes/revert/CTP.
- `tools/chrono_trigger_ctext.py` — status/audit/deploy/deactivate/undeploy.
- `tools/chrono_trigger_event.py` — show, exact fixed-width `set-args`, named `set-fields`.
- `tools/chrono_trigger_palette.py` — scene/world palette show/set.
- `tools/chrono_trigger_map.py` — scene/world L1/L2 PNG rendering.
- `tools/chrono_trigger_inventory.py` — ARC1 index-only gameplay-family discovery.

## Format evidence

- ChronoMod: <https://github.com/jimzrt/ChronoMod>
- CTViewer: <https://github.com/GitExl/CTViewer>
- Temporal Redux: <https://github.com/OnemusCT/temporal-redux>
- CTExt: <https://github.com/TheRealBiggs/ctext>

## Validation

The dedicated workflow installs the host smoke's import dependencies, compiles every Chrono plugin/CLI module, validates the descriptor, runs all `test_chrono_trigger_*.py` regressions, executes the real managed plugin smoke against a synthetic Steam ARC1 install, and syntax-checks the editor JavaScript.

## Remaining high-value work

1. Wire named fixed-width Atel editors into the desktop Events UI; variable/unresolved commands stay read-only.
2. Add scene L3/animated-tile rendering and correct PC main/sub-screen blend/priority composition.
3. Add the existing raster renderers to desktop map previews.
4. Run the resource-family inventory against a current real Steam install and reverse-engineer battle/enemy/item/tech stats from actual PC paths before adding those editors.
5. Keep ARC1 rebuilding as a fallback experiment only after real-install round-trip validation; loose CTExt/CTP remains the default deployment model.
