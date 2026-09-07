# FF7 edition parity and naming

The two supported FF7 Steam products intentionally share one editing implementation under `games/ff7`.

- `ff7-2013` remains a thin installation/identity adapter and must not acquire its own editor, server, parsers or writers.
- Equivalent source data must expose the same editor categories, fields, Data Map surface and capabilities and must serialize the same semantic edits to identical FF7 binary output.
- Edition-specific differences are limited to installation/layout discovery, process/launch identity, display identity and explicitly guarded executable profiles/runtime behavior.
- CI enforces this contract through `tools/verify_ff7_edition_parity.py`.

Requested display names:
- 2013 product: `Final Fantasy 7 (Original)`
- 2026 product: `Final Fantasy 7 (Completely Pointless 2026 Re-Release That Really Should Have Just Been A Patch)`
