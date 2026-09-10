# #461 — Steam collection plugin

Status: actionable. One branch/PR: `feature/ffx-x2-plugin` / draft PR #462.

## Proven inputs

- Steam collection uses app `359870`, launcher `FFX&X-2_LAUNCHER.exe`, games `FFX.exe` / `FFX-2.exe`, and `data/FFX_Data.vbf` / `data/FFX2_Data.vbf`.
- `michivi/vbf-fs` (BSD-3-Clause) establishes the VBF header, name/entry/block tables, 64 KiB blocks, zlib block behavior and trailing header MD5.
- Fahrenheit supports file-only mods under `fahrenheit/mods/<id>`, `mods/loadorder`, and External File Loader roots `efl/x` / `efl/x2`.
- Real VBF names can use raw `ffx_ps2/...` paths while Fahrenheit addresses them through virtual `FFX_Data/...` / `FFX2_Data/...` roots; Lexeditor normalizes that boundary explicitly.
- `Karifean/FFXDataParser` cross-checks the FFX `u16` fixed-record container, the FFX-2 `u32` container, and proved structured fields. It models FFX `command.bin`, `item.bin`, `monmagic1.bin`, and `monmagic2.bin` with animation IDs at `+0x10/+0x12`, `0x60` records for command/item and `0x5C` records for monster magic.
- `osdanova/FFXProjectEditor` independently identifies those four English/US files under `new_uspc/battle/kernel`; its serialized command layout places four four-byte text references before the two animation IDs and distinguishes the four-byte player extension from monster magic, independently agreeing with the same offsets/sizes.
- `HeartlessSeph/FFX2-010-Templates` independently establishes the FFX-2 `accessory.bin` `0x54` record layout used as a factual format cross-check.
- Fahrenheit Stage 0 accepts `fhstage0.exe {EXECUTABLE_TO_LAUNCH} {ARGS}`. Fahrenheit's docs launch FFX as `fhstage0.exe ..\..\FFX.exe`; Stage 0 resolves `fhstage1.dll` by relative name, so the required working directory is `<game>/fahrenheit/bin`.

No source from the reverse-engineering references is copied into Lexeditor except the separately noticed BSD-licensed VBF reference where permitted; the other projects are factual cross-checks only.

## Implemented in this PR

- Read-only validated VBF parser/indexer with safe decompression, header/path hash checks and path-safety enforcement.
- Searchable archive API for both games with raw-to-canonical Fahrenheit EFL normalization.
- Byte-exact extraction into project overlays, refusing unsafe paths and unintended overwrites.
- **Eleven conservative FFX structured tables**:
  - `takara.bin` — reward kind/quantity/type.
  - `item_rate.bin` — item/command gil prices.
  - `arms_rate.bin` — auto-ability gil prices.
  - `ctb_base.bin` — tick speed / ICV bonus.
  - `prepare.bin` — Rikku Mix result matrix.
  - `item_shop.bin` — 16 item/command slots.
  - `arms_shop.bin` — 16 gear slots.
  - `new_uspc/battle/kernel/command.bin` — animation IDs only (`+0x10/+0x12`, `0x60` records).
  - `new_uspc/battle/kernel/item.bin` — animation IDs only (`+0x10/+0x12`, `0x60` records).
  - `new_uspc/battle/kernel/monmagic1.bin` — animation IDs only (`+0x10/+0x12`, `0x5C` records).
  - `new_uspc/battle/kernel/monmagic2.bin` — animation IDs only (`+0x10/+0x12`, `0x5C` records).
- The four FFX ability-animation tables share one strict implementation and one UI selector. Unknown table names and extra edit fields are rejected; all bytes outside the two u16 animation IDs plus all trailing string data are preserved.
- **Two conservative FFX-2 structured tables**:
  - `new_uspc/battle/kernel/command.bin` — animation IDs only at `+0x08/+0x0A`.
  - `new_uspc/battle/kernel/accessory.bin` — four base ability IDs at `+0x18..+0x1F` and u32 price at `+0x20`; creature extension and strings remain opaque.
- All **13 structured tables** use exact VBF-header MD5 plus exact table SHA-256 stale-write protection.
- Structured saves are game-keyed and project-only: FFX -> `efl/x/FFX_Data/...`; FFX-2 -> `efl/x2/FFX2_Data/...`. Installed VBFs are never rewritten.
- Reversible Lexeditor-owned Fahrenheit file-only deployment with foreign/external-change guards and unrelated loadorder preservation.
- Private installed-game theme extraction/cache with fallback; no proprietary game assets are committed.
- Explicit collection-aware Play through Fahrenheit Stage 0:
  - `/api/play` accepts only exact `{"game":"x"}` or `{"game":"x2"}`.
  - no executable/path/command/argument input exists.
  - Stage 0 runs from `<game>/fahrenheit/bin` with only `..\..\FFX.exe` or `..\..\FFX-2.exe`.
  - the Square Enix collection launcher is never used.
- `/api/launch`, dashboard state, Data Map, and explicit **Play FFX / Play FFX-2** UI controls expose fixed launch readiness.
- Read-only real-install verifier: `python -m games.ffx_x2.verify_install`.
  - validates both actual installed VBFs;
  - resolves raw/canonical source paths;
  - parses every currently claimed structured table with production parsers;
  - reports record counts/sizes, exact source table SHA-256 and VBF metadata;
  - optionally requires Fahrenheit prerequisites with `--require-fahrenheit`;
  - performs no project write, deployment, VBF rewrite or launch.

## Regression guarantees

- FFX animation-family tests cover all four tables, exact expected record sizes, and byte-diff confinement to selected record `+0x10..+0x13` only.
- Managed tests save each of the four FFX animation tables through its canonical `efl/x/FFX_Data/...` project path and verify the source VBF SHA-256 remains unchanged.
- FFX-2 accessory regressions compare all bytes outside the six writable fields and preserve the complete creature extension and trailing strings.
- FFX-2 ability managed coverage proves project save -> `efl/x2` deploy -> loadorder preservation -> revert while the source VBF remains byte-identical.
- Play API tests patch only the process-execution boundary and reject generic commands, paths, args, aliases, extra keys, wrong types and non-object bodies without spawning a game.
- Install-verifier regressions exercise valid raw-path resolution, report metadata, missing-table failure, and invalid-VBF failure.

## Remaining actionable work

- Continue only through independently documented FFX/FFX-2 formats; unknown fields stay opaque. Do not add a generic hex editor.
- Research additional FFX kernel families only when at least two independent sources agree on the writable layout/semantics.
- Expand FFX-2 only through independently proved fields; localized strings, accessory creature-extension fields and other command fields remain intentionally untouched.
- Convert recognized non-browser-ready font atlases, menu textures and UI-audio banks only when a proved/local conversion path exists.
- Consider Fahrenheit helper/version management separately if Lexeditor should install/update it rather than merely interoperate with an existing setup.
- On a real Steam collection, run the read-only verifier and capture actual VBF inventories/record sizes, then test one harmless EFL replacement in each game and actual **Play FFX / Play FFX-2** Stage 0 startup plus deploy/revert acceptance.

Do not close #461 from synthetic/API/CI evidence alone. Real installed-game and in-game acceptance remain the draft exit criteria.
