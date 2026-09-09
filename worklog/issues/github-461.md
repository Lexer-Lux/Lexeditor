# #461 — Steam collection plugin

Status: actionable. One branch/PR: `feature/ffx-x2-plugin`.

## Proven inputs

- Steam collection uses app `359870`, launcher `FFX&X-2_LAUNCHER.exe`, games `FFX.exe` / `FFX-2.exe`, and `data/FFX_Data.vbf` / `data/FFX2_Data.vbf`.
- `michivi/vbf-fs` (BSD-3-Clause) establishes the VBF header, name/entry/block tables, 64 KiB blocks, zlib block behavior and trailing header MD5.
- Fahrenheit explicitly supports file-only mods. A mod lives under `fahrenheit/mods/<id>`, has `<id>.manifest.json`, is named in `mods/loadorder`, and EFL replacements mirror VBF paths under `efl/x` or `efl/x2`.

## Implemented in this PR

- Read-only VBF parser/indexer with structural/hash validation and safe decompression.
- Searchable archive API for both games.
- One-file extraction into project EFL overlays, refusing to overwrite changed project data.
- Reversible Lexeditor-owned Fahrenheit file-only deployment with foreign/external-change guards.
- Shared-shell archive browser, Data Map, install/project/deployment status.
- Synthetic smoke and regression coverage.

## Remaining actionable work

- Add first structured gameplay datasets, starting with well-documented FFX kernel/Excel families rather than exposing a generic hex editor.
- Establish corresponding FFX-2 record layouts.
- Add Fahrenheit helper/version management if Lexeditor is going to install it rather than merely interoperate with an existing installation.
- Add a collection-aware Play path that can intentionally launch either `FFX.exe` or `FFX-2.exe` through Fahrenheit Stage 0.
- Use a real Steam installation to verify VBF inventory assumptions, UI performance on full archive counts, one harmless EFL replacement in each game, and deploy/revert acceptance. Do not close #461 from CI alone.
