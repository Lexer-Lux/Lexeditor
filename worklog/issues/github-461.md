# #461 — Steam collection plugin

Status: actionable. One branch/PR: `feature/ffx-x2-plugin`.

## Proven inputs

- Steam collection uses app `359870`, launcher `FFX&X-2_LAUNCHER.exe`, games `FFX.exe` / `FFX-2.exe`, and `data/FFX_Data.vbf` / `data/FFX2_Data.vbf`.
- `michivi/vbf-fs` (BSD-3-Clause) establishes the VBF header, name/entry/block tables, 64 KiB blocks, zlib block behavior and trailing header MD5.
- Fahrenheit explicitly supports file-only mods. A mod lives under `fahrenheit/mods/<id>`, has `<id>.manifest.json`, is named in `mods/loadorder`, and EFL replacements mirror game-facing VBF paths under `efl/x` or `efl/x2`.
- Real VBF names can use raw `ffx_ps2/...` paths while Fahrenheit addresses them through the virtual `FFX_Data/...` / `FFX2_Data/...` roots; the plugin normalizes that boundary explicitly.
- `FFXDataParser` is a research cross-check for the FFX `u16` fixed-record container, the FFX-2 `u32` fixed-record container and the proved `command.bin` fields. Its source is not copied into Lexeditor.
- `HeartlessSeph/FFX2-010-Templates` independently establishes the `accessory.bin` 0x54-byte record layout used as a factual format cross-check; its template source is not copied.
- Fahrenheit Stage 0 accepts `fhstage0.exe {EXECUTABLE_TO_LAUNCH} {ARGS}`; Fahrenheit's own build docs demonstrate targeting `FFX.exe` directly.

## Implemented in this PR

- Read-only VBF parser/indexer with structural, header-hash and per-path-hash validation plus safe decompression.
- Searchable archive API for both games, including raw-to-virtual EFL path normalization.
- One-file extraction into project EFL overlays, refusing to overwrite changed project data.
- Seven conservative FFX structured editors: treasures, item prices, auto-ability prices, CTB timing, Rikku Mix results, item shops and gear shops.
- Shared binary/UI implementations where formats truly match: four-byte u32 price tables and 0x22-byte/16-slot shop tables.
- Separate validated FFX-2 `u32` fixed-record table reader (`0x20` header/record start).
- FFX-2 `new_uspc/battle/kernel/command.bin`: writes only animation IDs at record offsets `+0x08/+0x0A`; string refs, unknown bytes and trailing localized strings are preserved.
- FFX-2 `new_uspc/battle/kernel/accessory.bin`: requires the proved zero record origin and `0x54` record size; writes only four base ability IDs at `+0x18..+0x1F` and the u32 price at `+0x20`; all other base fields, the `+0x24..+0x53` creature extension and trailing strings are preserved.
- Accessory regressions compare every byte outside the writable fields and include managed raw-VBF → canonical `efl/x2/FFX2_Data/...` save coverage.
- FFX-2 ability managed coverage proves project save → Fahrenheit `efl/x2` deploy → loadorder preservation → revert while the source VBF hash remains unchanged.
- Structured saves use exact VBF-header and table-byte baselines so stale/external changes fail closed.
- Game-keyed structured service writes FFX under `efl/x/FFX_Data/...` and FFX-2 under `efl/x2/FFX2_Data/...`.
- Reversible Lexeditor-owned Fahrenheit file-only deployment with foreign/external-change guards.
- Private installed-game theme extraction/cache with safe fallback and no bundled proprietary assets.
- Nine structured UI views are now integrated: seven FFX plus X-2 Abilities and X-2 Accessories. The accessory panel is a plugin-specific extension loaded by the stable shared shell.
- The nine-editor checkpoint passes FFX-X2 checks on Windows and Ubuntu, Shared UI contract, and Shared UI visual acceptance.

## Remaining actionable work

- Add a collection-aware Play path that intentionally launches either `FFX.exe` or `FFX-2.exe` through Fahrenheit Stage 0.
- Continue through well-documented FFX kernel families rather than exposing a generic hex editor.
- Expand FFX-2 only through independently proved record fields; localized string editing, creature-extension accessory fields and other command fields remain intentionally untouched.
- Convert recognized non-browser-ready font atlases, menu textures and UI-audio banks only when a proved/local conversion path is available.
- Add Fahrenheit helper/version management if Lexeditor is going to install it rather than merely interoperate with an existing installation.
- Use a real Steam installation to verify actual VBF inventories and record sizes, UI performance on full archive counts, one harmless structured/EFL replacement in each game, and deploy/revert acceptance. Do not close #461 from CI alone.
