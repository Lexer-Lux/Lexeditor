# #461 — Steam collection plugin

Status: actionable. One branch/PR: `feature/ffx-x2-plugin` / draft PR #462.

## Proven inputs

- Steam collection uses app `359870`, launcher `FFX&X-2_LAUNCHER.exe`, games `FFX.exe` / `FFX-2.exe`, and `data/FFX_Data.vbf` / `data/FFX2_Data.vbf`.
- `michivi/vbf-fs` (BSD-3-Clause) establishes the VBF header, name/entry/block tables, 64 KiB blocks, zlib block behavior and trailing header MD5.
- Fahrenheit supports file-only mods under `fahrenheit/mods/<id>`, `mods/loadorder`, and External File Loader roots `efl/x` / `efl/x2`.
- Real VBF names can use raw `ffx_ps2/...` paths while Fahrenheit addresses them through virtual `FFX_Data/...` / `FFX2_Data/...` roots; Lexeditor normalizes that boundary explicitly.
- `Karifean/FFXDataParser` cross-checks the FFX `u16` fixed-record container, FFX-2 `u32` container and proved structured fields. It models FFX `command.bin`, `item.bin`, `monmagic1.bin`, and `monmagic2.bin` with animation IDs at `+0x10/+0x12`, `0x60` records for command/item and `0x5C` records for monster magic.
- `osdanova/FFXProjectEditor` independently identifies those four English/US files under `new_uspc/battle/kernel` and independently agrees on the command animation offsets/size distinction.
- FFXDataParser identifies `new_uspc/battle/kernel/a_ability.bin` as `0x6C` records and maps the five element bytes at `+0x11..+0x15` as Strike, Absorb, Immune, Resist and Weak.
- Fahrenheit independently asserts `FFX.AutoAbility` is `0x6C` for `a_ability.bin`; its sequential struct places SOS at `+0x10` followed by the same five element fields, and its `ElementFlags` defines Fire/Ice/Thunder/Water/Holy as bits 0..4.
- FFXDataParser defines `PlayerCharStatDataObject.LENGTH = 0x94` for localized `battle/kernel/ply_save.bin`, reading base HP/MP at `+0x04/+0x08` and STR/DEF/MAG/MDF/AGI/LCK/EVA/ACC at `+0x0C..+0x13`.
- Fahrenheit independently asserts `FFX.PlySave` is `0x94` for `ply_save.bin`; its sequential struct places one four-byte text offset first, then the same base HP, base MP and eight base-stat fields in the same order. The references diverge/identify later bytes differently enough that Lexeditor stops at `+0x13`.
- `HeartlessSeph/FFX2-010-Templates` independently establishes the FFX-2 `accessory.bin` `0x54` record layout.
- Fahrenheit Stage 0 accepts `fhstage0.exe {EXECUTABLE_TO_LAUNCH} {ARGS}`. Fahrenheit's docs launch FFX as `fhstage0.exe ..\..\FFX.exe`; Stage 0 resolves `fhstage1.dll` by relative name, so cwd must be `<game>/fahrenheit/bin`.

The reverse-engineering projects are factual format cross-checks; their source is not copied into the structured editor implementations.

## Implemented in this PR

- Read-only validated VBF parser/indexer with safe decompression, header/path hash checks and path-safety enforcement.
- Searchable archive API for both games with raw-to-canonical Fahrenheit EFL normalization.
- Byte-exact extraction into project overlays, refusing unsafe paths and unintended overwrites.
- **Thirteen conservative FFX structured tables**:
  - `takara.bin` — reward kind/quantity/type.
  - `item_rate.bin` — item/command gil prices.
  - `arms_rate.bin` — auto-ability gil prices.
  - `new_uspc/battle/kernel/a_ability.bin` — known elemental masks only at `+0x11..+0x15`; upper three bits in each byte are preserved and SOS/status/effect/icon/group/string fields remain opaque.
  - `new_uspc/battle/kernel/ply_save.bin` — base HP/MP at `+0x04/+0x08` and eight base stats at `+0x0C..+0x13`; text metadata before them and every byte from `+0x14` onward remain opaque.
  - `ctb_base.bin` — tick speed / ICV bonus.
  - `prepare.bin` — Rikku Mix result matrix.
  - `item_shop.bin` — 16 item/command slots.
  - `arms_shop.bin` — 16 gear slots.
  - `new_uspc/battle/kernel/command.bin` — animation IDs only (`+0x10/+0x12`, `0x60` records).
  - `new_uspc/battle/kernel/item.bin` — animation IDs only (`+0x10/+0x12`, `0x60` records).
  - `new_uspc/battle/kernel/monmagic1.bin` — animation IDs only (`+0x10/+0x12`, `0x5C` records).
  - `new_uspc/battle/kernel/monmagic2.bin` — animation IDs only (`+0x10/+0x12`, `0x5C` records).
- The four FFX ability-animation tables share one strict implementation and one fixed UI selector. Unknown table names and extra edit fields are rejected.
- The auto-ability element editor exposes only five known element bits per behavior. Save logic preserves the upper three unknown bits of each source byte.
- The player base-stat editor accepts only the ten independently agreed values; there is no character-name mapping, AP/current-state editor, or access to the disputed/later `ply_save.bin` region.
- **Two conservative FFX-2 structured tables**:
  - `new_uspc/battle/kernel/command.bin` — animation IDs only at `+0x08/+0x0A`.
  - `new_uspc/battle/kernel/accessory.bin` — four base ability IDs at `+0x18..+0x1F` and u32 price at `+0x20`; creature extension and strings remain opaque.
- All **15 structured tables** use exact VBF-header MD5 plus exact table SHA-256 stale-write protection.
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
  - `--hash-archives` optionally streams complete installed VBFs through SHA-256;
  - `--require-fahrenheit` also gates on Stage 0/Stage 1 and both executables;
  - performs no project write, deployment, VBF rewrite or launch.
- `worklog/acceptance/ffx-x2/README.md` defines the remaining real-install draft-exit procedure, starting with byte-identical EFL replacements before any gameplay edit.

## Regression guarantees

- FFX animation-family tests cover all four tables, exact expected record sizes, fixed selector validation, cross-table stale-baseline rejection, and byte-diff confinement to selected record `+0x10..+0x13` only.
- Auto-ability element tests seed unknown high bits and unrelated opaque bytes, then prove only selected record `+0x11..+0x15` low five bits can change; SOS, byte `+0x68`, other records and trailing strings stay byte-identical.
- Player-stat tests prove the parser exposes only the independently agreed base prefix and that a save can change bytes only in selected record `+0x04..+0x13`; the text reference prefix, disputed `+0x14` region, rest of the record, other records and trailing strings stay byte-identical.
- Managed auto-ability and player-stat coverage save only to canonical `efl/x/FFX_Data/...` project paths and verify the installed VBF SHA-256 is unchanged.
- Managed tests save each of the four FFX animation tables through its canonical project path and likewise leave the source VBF unchanged.
- FFX-2 accessory regressions compare all bytes outside the six writable fields and preserve the complete creature extension and trailing strings.
- FFX-2 ability managed coverage proves project save -> `efl/x2` deploy -> loadorder preservation -> revert while the source VBF remains byte-identical.
- Play API tests patch only the process-execution boundary and reject generic commands, paths, args, aliases, extra keys, wrong types and non-object bodies without spawning a game.
- Install-verifier regressions cover raw-path resolution/report metadata, missing-table failure, invalid-VBF failure and optional full-file SHA-256 capture.

## Remaining actionable work

- Continue only through independently documented FFX/FFX-2 formats; unknown fields stay opaque. Do not add a generic hex editor.
- Do not widen `a_ability.bin` or `ply_save.bin` merely because more bytes have labels in one source; only independently agreed semantics should become writable.
- Expand FFX-2 only through independently proved fields; localized strings, accessory creature-extension fields and other command fields remain intentionally untouched.
- Convert recognized non-browser-ready font atlases, menu textures and UI-audio banks only when a proved/local conversion path exists.
- Consider Fahrenheit helper/version management separately if Lexeditor should install/update it rather than merely interoperate with an existing setup.
- On a real Steam collection, run the verifier with `--hash-archives`, capture actual inventories/record sizes, then test one byte-identical EFL replacement in each game, actual **Play FFX / Play FFX-2** Stage 0 startup, and reversible structured round trips.

Do not close #461 or mark PR #462 ready from synthetic/API/CI evidence alone. Real installed-game and in-game acceptance remain the draft exit criteria.
