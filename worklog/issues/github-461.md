# #461 — Steam collection plugin

Status: actionable. One branch/PR: `feature/ffx-x2-plugin`.

## Proven inputs

- Steam collection uses app `359870`, launcher `FFX&X-2_LAUNCHER.exe`, games `FFX.exe` / `FFX-2.exe`, and `data/FFX_Data.vbf` / `data/FFX2_Data.vbf`.
- `michivi/vbf-fs` (BSD-3-Clause) establishes the VBF header, name/entry/block tables, 64 KiB blocks, zlib block behavior and trailing header MD5.
- Fahrenheit explicitly supports file-only mods. A mod lives under `fahrenheit/mods/<id>`, has `<id>.manifest.json`, is named in `mods/loadorder`, and EFL replacements mirror game-facing VBF paths under `efl/x` or `efl/x2`.
- Real VBF names can use raw `ffx_ps2/...` paths while Fahrenheit addresses them through the virtual `FFX_Data/...` / `FFX2_Data/...` roots; the plugin normalizes that boundary explicitly.
- `FFXDataParser` is a research cross-check for the FFX `u16` fixed-record container, the FFX-2 `u32` fixed-record container and proved structured fields. Its source is not copied into Lexeditor.
- `osdanova/FFXProjectEditor` independently cross-checks the FFX English/US `command.bin` path, `0x60` command-record size and animation IDs at record offsets `+0x10/+0x12`; its source is not copied.
- `HeartlessSeph/FFX2-010-Templates` independently establishes the `accessory.bin` 0x54-byte record layout used as a factual format cross-check; its template source is not copied.
- Fahrenheit Stage 0 accepts `fhstage0.exe {EXECUTABLE_TO_LAUNCH} {ARGS}`. Fahrenheit's own docs launch FFX as `fhstage0.exe ..\..\FFX.exe`, and Stage 0 resolves `fhstage1.dll` by relative name, so the required working directory is `<game>/fahrenheit/bin`.

## Implemented in this PR

- Read-only VBF parser/indexer with structural, header-hash and per-path-hash validation plus safe decompression.
- Searchable archive API for both games, including raw-to-virtual EFL path normalization.
- One-file extraction into project EFL overlays, refusing to overwrite changed project data.
- Eight conservative FFX structured editors: treasures, item prices, auto-ability prices, CTB timing, Rikku Mix results, item shops, gear shops and English/US command animation IDs.
- FFX `new_uspc/battle/kernel/command.bin`: requires the independently cross-checked `0x60` record size and writes only animation IDs at record offsets `+0x10/+0x12`; every other record byte and trailing string data are preserved.
- FFX command regressions compare all bytes outside the four writable animation bytes, reject extra edit fields, prove raw-VBF → canonical `efl/x/FFX_Data/...` project save, and verify the installed VBF hash is unchanged.
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
- Ten structured UI views are integrated: eight FFX plus X-2 Abilities and X-2 Accessories. Additional panels remain plugin-specific extensions loaded by the stable shared shell rather than expanding the core HTML indefinitely.
- Collection-aware Play is wired through Fahrenheit Stage 0. `/api/play` accepts only the exact bodies `{"game":"x"}` or `{"game":"x2"}`; there is no executable, path, command or argument input.
- Play never uses `FFX&X-2_LAUNCHER.exe`. It requires `fhstage0.exe`, `fhstage1.dll` and the selected game executable, runs Stage 0 with cwd `<game>/fahrenheit/bin`, and passes only the fixed relative target `..\..\FFX.exe` or `..\..\FFX-2.exe`.
- `/api/launch` and the dashboard expose Stage 0/Stage 1, per-title executable and Windows-host readiness; `fahrenheit-launch` is advertised in plugin capabilities and the Data Map.
- The UI exposes explicit **Play FFX** and **Play FFX-2** controls and disables them when the fixed launch contract is not actionable.
- API regressions run the loopback service, patch only the launch execution boundary, prove both fixed keys reach it, and reject extra arguments, paths, launcher names, uppercase aliases, wrong types and non-object request bodies without spawning a game.
- The Play checkpoint passed FFX-X2 checks on Windows and Ubuntu, Shared UI contract, and Shared UI visual acceptance. The later ten-editor head also passes the Windows/Ubuntu FFX-X2 matrix; keep CI evidence distinct from real in-game acceptance.

## Remaining actionable work

- Continue through well-documented FFX kernel families rather than exposing a generic hex editor. Fields whose independent descriptions do not agree stay opaque.
- Expand FFX-2 only through independently proved record fields; localized string editing, creature-extension accessory fields and other command fields remain intentionally untouched.
- Convert recognized non-browser-ready font atlases, menu textures and UI-audio banks only when a proved/local conversion path is available.
- Add Fahrenheit helper/version management if Lexeditor is going to install it rather than merely interoperate with an existing installation.
- Use a real Steam installation to verify actual VBF inventories and record sizes, UI performance on full archive counts, one harmless structured/EFL replacement in each game, and real **Play FFX / Play FFX-2** Stage 0 startup plus deploy/revert acceptance. Do not close #461 from CI alone.
