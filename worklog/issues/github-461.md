# #461 — Steam collection plugin

Status: actionable. One branch/PR: `feature/ffx-x2-plugin`.

## Proven inputs

- Steam collection uses app `359870`, launcher `FFX&X-2_LAUNCHER.exe`, games `FFX.exe` / `FFX-2.exe`, and `data/FFX_Data.vbf` / `data/FFX2_Data.vbf`.
- `michivi/vbf-fs` (BSD-3-Clause) establishes the VBF header, name/entry/block tables, 64 KiB blocks, zlib block behavior and trailing header MD5.
- Fahrenheit explicitly supports file-only mods. A mod lives under `fahrenheit/mods/<id>`, has `<id>.manifest.json`, is named in `mods/loadorder`, and EFL replacements mirror game-facing VBF paths under `efl/x` or `efl/x2`.
- Real VBF names can use raw `ffx_ps2/...` paths while Fahrenheit addresses them through the virtual `FFX_Data/...` / `FFX2_Data/...` roots; the plugin normalizes that boundary explicitly.
- `FFXDataParser` is a research cross-check for the common FFX fixed-record container and the proved fields in `takara.bin` and `item_shop.bin`. Its source is not copied into Lexeditor.

## Implemented in this PR

- Read-only VBF parser/indexer with structural, header-hash and per-path-hash validation plus safe decompression.
- Searchable archive API for both games, including raw-to-virtual EFL path normalization.
- One-file extraction into project EFL overlays, refusing to overwrite changed project data.
- Common validated FFX fixed-record table reader.
- Structured `takara.bin` treasure editor for reward kind, quantity and type ID only; unknown record bytes and trailing data are preserved.
- Structured `item_shop.bin` editor for sixteen item/command ID slots per shop; the leading unused/legacy rate field is preserved read-only.
- Structured saves use exact VBF-header and table-byte baselines so stale/external changes fail closed.
- Reversible Lexeditor-owned Fahrenheit file-only deployment with foreign/external-change guards.
- Private installed-game theme extraction/cache with safe fallback and no bundled proprietary assets.
- Shared-shell structured editors, archive browser, Data Map, install/project/deployment status.
- Cross-platform synthetic smoke and dedicated VBF/path/deployment/treasure/item-shop regressions.

## Remaining actionable work

- Continue through well-documented FFX kernel families rather than exposing a generic hex editor; good candidates include gear shops and other simple fixed-record tables.
- Establish corresponding FFX-2 record layouts before exposing any FFX-2 structured write path.
- Convert recognized non-browser-ready font atlases, menu textures and UI-audio banks only when a proved/local conversion path is available.
- Add Fahrenheit helper/version management if Lexeditor is going to install it rather than merely interoperate with an existing installation.
- Add a collection-aware Play path that can intentionally launch either `FFX.exe` or `FFX-2.exe` through Fahrenheit Stage 0.
- Use a real Steam installation to verify actual VBF inventories and record sizes, UI performance on full archive counts, one harmless structured/EFL replacement in each game, and deploy/revert acceptance. Do not close #461 from CI alone.
