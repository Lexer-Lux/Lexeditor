# #461 — Steam collection plugin

Status: actionable. One branch/PR: `feature/ffx-x2-plugin`.

## Proven inputs

- Steam collection uses app `359870`, launcher `FFX&X-2_LAUNCHER.exe`, games `FFX.exe` / `FFX-2.exe`, and `data/FFX_Data.vbf` / `data/FFX2_Data.vbf`.
- `michivi/vbf-fs` (BSD-3-Clause) establishes the VBF header, name/entry/block tables, 64 KiB blocks, zlib block behavior and trailing header MD5.
- Fahrenheit explicitly supports file-only mods. A mod lives under `fahrenheit/mods/<id>`, has `<id>.manifest.json`, is named in `mods/loadorder`, and EFL replacements mirror game-facing VBF paths under `efl/x` or `efl/x2`.
- Real VBF names can use raw `ffx_ps2/...` paths while Fahrenheit addresses them through the virtual `FFX_Data/...` / `FFX2_Data/...` roots; the plugin normalizes that boundary explicitly.
- `FFXDataParser` is a research cross-check for the FFX `u16` fixed-record container, the FFX-2 `u32` fixed-record container and the proved `command.bin` fields. Its source is not copied into Lexeditor.
- `HeartlessSeph/FFX2-010-Templates` independently establishes the `accessory.bin` 0x54-byte record layout used as a factual format cross-check; its template source is not copied.

## Implemented in this PR

- Read-only VBF parser/indexer with structural, header-hash and per-path-hash validation plus safe decompression.
- Searchable archive API for both games, including raw-to-virtual EFL path normalization.
- One-file extraction into project EFL overlays, refusing to overwrite changed project data.
- Common validated FFX fixed-record table reader.
- Structured `takara.bin` treasure editor for reward kind, quantity and type ID only; unknown record bytes and trailing data are preserved.
- Shared four-byte u32-price core used by `item_rate.bin` (`0x2000+` item/command IDs) and `arms_rate.bin` (`0x8000+` auto-ability IDs).
- Structured `ctb_base.bin` editor for tick speed and ICV bonus by Agility, with derived ICV ranges shown in the UI.
- Structured `prepare.bin` editor for the 112 × N Rikku Mix result-command matrix; only selected 16-bit result cells are written.
- Shared validated `0x22`-byte / 16-slot FFX shop-table core.
- Structured `item_shop.bin` editor for sixteen item/command ID slots per shop; the leading unused/legacy rate field is preserved read-only.
- Structured `arms_shop.bin` editor for sixteen gear-index slots per shop with the same preservation boundary.
- Separate validated FFX-2 `u32` fixed-record table reader (`0x20` header/record start).
- FFX-2 `new_uspc/battle/kernel/command.bin`: writes only animation IDs at record offsets `+0x08/+0x0A`; string refs, unknown bytes and trailing localized strings are preserved.
- FFX-2 `new_uspc/battle/kernel/accessory.bin`: requires the proved zero record origin and `0x54` record size; writes only four base ability IDs at `+0x18..+0x1F` and the u32 price at `+0x20`; all other base fields, the `+0x24..+0x53` creature extension and trailing strings are preserved.
- Accessory regressions compare every byte outside the writable fields and include managed raw-VBF → canonical `efl/x2/FFX2_Data/...` save coverage.
- FFX-2 ability managed coverage additionally proves project save → Fahrenheit `efl/x2` deploy → loadorder preservation → revert while the source VBF hash remains unchanged.
- Structured saves use exact VBF-header and table-byte baselines so stale/external changes fail closed.
- Game-keyed structured service writes FFX under `efl/x/FFX_Data/...` and FFX-2 under `efl/x2/FFX2_Data/...`.
- Reversible Lexeditor-owned Fahrenheit file-only deployment with foreign/external-change guards.
- Private installed-game theme extraction/cache with safe fallback and no bundled proprietary assets.
- Seven FFX shared-shell structured views plus the X-2 ability view; the X-2 accessory backend/Data Map is integrated and its dedicated panel is the next UI-only slice.
- Cross-platform synthetic smoke and dedicated VBF/path/deployment/structured-table regressions, including managed raw-VBF-to-canonical-EFL save coverage for both games.

## Remaining actionable work

- Finish the dedicated FFX-2 accessory panel without broadening the writable field set.
- Continue through well-documented FFX kernel families rather than exposing a generic hex editor.
- Expand FFX-2 only through independently proved record fields; localized string editing, creature-extension accessory fields and other command fields remain intentionally untouched.
- Convert recognized non-browser-ready font atlases, menu textures and UI-audio banks only when a proved/local conversion path is available.
- Add Fahrenheit helper/version management if Lexeditor is going to install it rather than merely interoperate with an existing installation.
- Add a collection-aware Play path that can intentionally launch either `FFX.exe` or `FFX-2.exe` through Fahrenheit Stage 0.
- Use a real Steam installation to verify actual VBF inventories and record sizes, UI performance on full archive counts, one harmless structured/EFL replacement in each game, and deploy/revert acceptance. Do not close #461 from CI alone.
