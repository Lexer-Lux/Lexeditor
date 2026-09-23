# #461 — Steam collection plugin

Status: awaiting real-install acceptance. One branch/PR: `feature/ffx-x2-plugin` / draft PR #462.

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
- `HeartlessSeph/FFX2-010-Templates` independently establishes the FFX-2 `accessory.bin` `0x54` layout and the sixteen required-ability / ability pairs in `job.bin`; Fahrenheit independently fixes `Job` at `0xE4` bytes with the same 32-u16 ability-tree region after its 46-byte stat-growth block.
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
- **Three conservative FFX-2 structured tables**:
  - `new_uspc/battle/kernel/command.bin` — animation IDs only at `+0x08/+0x0A`.
  - `new_uspc/battle/kernel/accessory.bin` — four base ability IDs at `+0x18..+0x1F` and u32 price at `+0x20`; creature extension and strings remain opaque.
  - `new_uspc/battle/kernel/job.bin` — sixteen required-ability / learned-ability pairs at `+0x3C..+0x7B`; stat growth, weapons, creature data, flags and strings remain opaque.
- All **16 structured tables** use exact VBF-header MD5 plus exact table SHA-256 stale-write protection.
- Structured saves are game-keyed and project-only: FFX -> `efl/x/FFX_Data/...`; FFX-2 -> `efl/x2/FFX2_Data/...`. Installed VBFs are never rewritten.
- Reversible Lexeditor-owned Fahrenheit file-only deployment with foreign/external-change guards and unrelated loadorder preservation.
- Private installed-game theme extraction/cache with fallback; no proprietary game assets are committed.
- Explicit collection-aware Play through Fahrenheit Stage 0:
  - `/api/play` accepts only exact `{"game":"x"}` or `{"game":"x2"}`.
  - no executable/path/command/argument input exists.
  - Stage 0 runs from `<game>/fahrenheit/bin` with only `..\..\FFX.exe` or `..\..\FFX-2.exe`.
  - Stage 0 is spawned with Windows `CREATE_NO_WINDOW`; Lexeditor does not allocate a helper console.
  - the Square Enix collection launcher is never used.
- `/api/launch`, dashboard state, Data Map, and explicit **Play FFX / Play FFX-2** UI controls expose fixed launch readiness.
- Read-only real-install verifier: `python -m games.ffx_x2.verify_install`.
  - validates both actual installed VBFs;
  - resolves raw/canonical source paths;
  - parses every currently claimed structured table with production parsers;
  - reports record counts/sizes, exact source table SHA-256 and VBF metadata;
  - `--hash-archives` optionally streams complete installed VBFs through SHA-256;
  - `--require-fahrenheit` also gates the command exit status on Stage 0/Stage 1 and both executables;
  - `verificationPassed` records the requested verifier invocation result;
  - `acceptanceReady` is stricter and requires validated archive/structured coverage, full SHA-256 values for both installed VBFs, and all fixed Fahrenheit/game launch prerequisites;
  - performs no project write, deployment, VBF rewrite or launch.
- `worklog/acceptance/ffx-x2/run-verifier.ps1` runs the strict real-install command, writes UTF-8 acceptance JSON, fails unless `acceptanceReady` is true, and can compare both installed VBF header MD5/SHA-256 values against a baseline report after deploy/launch tests.
- `worklog/acceptance/ffx-x2/README.md` defines the remaining real-install draft-exit procedure, starting with byte-identical EFL replacements before any gameplay edit.

## Current shared-UI / guide audit

Reviewed against current `master` `72ee978`, not the older branch snapshots:

- `AGENTS.md` `41355ce` — workflow/test-readiness rules.
- `docs/ADDING_A_GAME.md` `7fe6d35` — markup-only page modules, shared UI budget, helper/update rules and acceptance ladder.
- `docs/UI-MANUAL.md` `14a3269` — Table + Detail identity/group/help semantics.
- `ui/component-catalog.js` `a11e52e` — shared component inventory.
- Blank gallery: `games/blank/editor.html` `b0b235d`, `editor.js` `bec94d0`, `editor.css` `4e01602`.
- RDR2 Table + Detail references: `items.js` `a42f987`, `loot.js` `5483171`, `crafting.js` `a92cd8c`, `effects.js` `ae814a1`.

Requirement / gap / evidence:

- **Markup-only page + relative modules:** done. FFX/X-2 uses markup-only `editor.html`, relative `editor.js` / `editor.css`, and the shared `PluginRequestHandler.send_page_module` route.
- **Shared shell / Info / Data Map:** done. Info and Data Map are shell actions, not content tabs; Data Map uses the shared integration icons and standard coverage vocabulary.
- **Shared UI budget:** done. FFX/X-2 HTML/JS/CSS contain zero local selectors naming `.lex-*` and zero hand-built table-row elements; the scoped workflow enforces that zero budget.
- **Every record list is paged Table + Detail:** done for all 16 structured tables and both archive browsers. The synthetic acceptance fixture uses 36 records per structured table and 520 archive entries so paging/search/sort/selection are multi-page behavior.
- **Cell editors + semantic controls:** done where semantics are proved. Numeric bounds match parser write guards; treasure kind is a fixed-choice select while preserving unknown existing values; elemental masks are decomposed switches. Opaque/unproved fields remain read-only or absent.
- **Identity / grouping / help:** record IDs are real table IDs; no row index is presented as a fabricated game ID. Detail groups are semantic (context, editable fields, shop inventories, ability pairs) and help explains game effect rather than repeating storage metadata.
- **Loading / empty / error:** page navigation clears to an explicit loading state; datasets have explicit empty and error states.
- **Tall panels / small windows / large UI scale:** acceptance checks the final dressphere ability pair and Mix partner 111 with the outer document fixed and the Detail body owning vertical scrolling. Desktop, 760px and 150% scale-equivalent captures are produced for inspection.
- **Save / discard / reopen:** synthetic acceptance exercises Table cell edit -> dirty -> discard and edit -> Save -> reload persistence. Production saves still use VBF-header MD5 + exact table SHA-256 stale-write guards and project-only writes.
- **Tweaks pagination:** not applicable. This plugin has no independently proved settings/tweak surface; all current writable data are records. No speculative Tweaks tab was invented.
- **Shared API transition:** current master removed `GamePlugin.subtitle` / `description`; the feature branch reconciles to that API and does not add replacement metadata.

### Fahrenheit helper/update audit

The current guide requires runtime helpers to be pinned, bundled, first-time installable, exposed through the shared Updates drawer, and unable to self-update.

Research checked Fahrenheit `v1.0.0-alpha11` (published 2026-09-19):

- release asset `fahrenheit_release_v1.0.0-alpha11.zip` publishes SHA-256 `ac51291edf0483f0f47be7c24b50bb2169c566722f384098d62433477674dc89`;
- Fahrenheit source is LGPL-3.0-or-later and the release is signed;
- Fahrenheit's own README separately says the repository `assets` folder may be used in Fahrenheit forks but not for other purposes;
- its runtime project copies `assets/*.ttf` into `resources/fonts` before the release script zips the complete deployment tree;
- the runtime GUI loads the resulting Noto Sans font files from `resources/fonts` at startup. The third-party notices identify those fonts as SIL OFL, but Lexeditor must not treat that as permission to redistribute Fahrenheit's restricted asset copies wholesale without a separately verified package provenance.

Therefore **the upstream release ZIP is not accepted as a Lexeditor-bundled helper as-is**. A stripped/minimal package is also not yet accepted: the exact signed runtime dependency set and replacement provenance for the required fonts have not been verified end-to-end. Registering only `helper_status` is not a safe partial solution because the shared installation manager marks a missing helper as **Broken** and prevents opening the editor, while this plugin can still safely edit project data without Fahrenheit installed.

Current safe behavior remains interoperability with an existing Fahrenheit installation; Play/deploy readiness remains gated separately. Helper Install/Repair and Updates-drawer registration stay blocked until a complete license-safe pinned package can be assembled and tested. Lexeditor does not invoke any Fahrenheit updater or perform automatic helper updates.

## Regression guarantees

- FFX animation-family tests cover all four tables, exact expected record sizes, fixed selector validation, cross-table stale-baseline rejection, and byte-diff confinement to selected record `+0x10..+0x13` only.
- Auto-ability element tests seed unknown high bits and unrelated opaque bytes, then prove only selected record `+0x11..+0x15` low five bits can change; SOS, byte `+0x68`, other records and trailing strings stay byte-identical.
- Player-stat tests prove the parser exposes only the independently agreed base prefix and that a save can change bytes only in selected record `+0x04..+0x13`; the text reference prefix, disputed `+0x14` region, rest of the record, other records and trailing strings stay byte-identical.
- Managed auto-ability and player-stat coverage save only to canonical `efl/x/FFX_Data/...` project paths and verify the installed VBF SHA-256 is unchanged.
- Managed tests save each of the four FFX animation tables through its canonical project path and likewise leave the source VBF unchanged.
- FFX-2 accessory regressions compare all bytes outside the six writable fields and preserve the complete creature extension and trailing strings.
- FFX-2 dressphere regressions constrain changes to selected four-byte ability-tree pairs and preserve stat-growth bytes, post-tree data, other records and trailing strings byte-for-byte.
- FFX-2 ability managed coverage proves project save -> `efl/x2` deploy -> loadorder preservation -> revert while the source VBF remains byte-identical.
- Play API tests patch only the process-execution boundary and reject generic commands, paths, args, aliases, extra keys, wrong types and non-object bodies without spawning a game.
- Stage 0 launch tests assert the fixed argv/cwd and Windows no-console process creation flag without launching the game.
- Install-verifier regressions cover raw-path resolution/report metadata, missing-table failure, invalid-VBF failure, optional full-file SHA-256 capture, strict draft-exit readiness, and fail-closed incomplete archive/launch maps.
- The Windows CI leg parses the acceptance PowerShell runner before the rest of the FFX/X-2 regression suite.

## Merge session (2026-09-23)

- Merged `feature/ffx-x2-plugin` into master oldest-first with HEAD shared-contract
  deletions kept on conflict.
- Fixed a real editor race: concurrent `renderGroup` calls joined a half-loaded
  dataset and rendered a stuck empty view. `ensureDataset`/`ensureArchive` now join
  the in-flight load (`games/ffx_x2/editor.js`). Fast tab switches are the repro.
- Repaired the browser harness: subtab center-clicks land on the `?` help at narrow
  widths (label shrinks to a sliver), so `_open_dataset` activates tabs by keyboard,
  asserts `aria-selected`, and waits for list auto-fit to settle before touching rows.
- Removed one `!important` split override from `games/ffx_x2/editor.css` (splitter
  default already matches); registered the `ffx_x2: 25` CSS ceiling, important 0.
- Cut chrono-trigger entries that leaked into this branch out of `ui/mod-loading.json`,
  `ui/credits.json`, `ui/credits-sources.json`; they return with the Chrono branch.
- Repaired page-module drift in `tools/verify_shared_ui_contract.py` (reads shell plus
  local modules) and `./`-relative paths in `tests/plugin_module_routes_check.py`.
- Gates green: FFX browser check (desktop/narrow/150pct), 115 FFX unit tests, CSS
  budget, shared UI contract, plugin/metadata/credits contracts, module routes, smoke.
- Merge adds 3 newly-green gate failures fixed; 17 unrelated master failures remain and
  belong to the cleanup pass, not this merge.

## Remaining actionable work

- Continue only through independently documented FFX/FFX-2 formats; unknown fields stay opaque. Do not add a generic hex editor.
- Do not widen `a_ability.bin` or `ply_save.bin` merely because more bytes have labels in one source; only independently agreed semantics should become writable.
- Expand FFX-2 only through independently proved fields; localized strings, accessory creature-extension fields and other command fields remain intentionally untouched.
- Convert recognized non-browser-ready font atlases, menu textures and UI-audio banks only when a proved/local conversion path exists.
- Consider Fahrenheit helper/version management separately if Lexeditor should install/update it rather than merely interoperate with an existing setup.
- On a real Steam collection, run `worklog/acceptance/ffx-x2/run-verifier.ps1` to capture the baseline, test one byte-identical EFL replacement in each game, verify actual **Play FFX / Play FFX-2** Stage 0 startup and reversible structured round trips, then rerun with `-BaselinePath` to prove both installed VBFs remained unchanged.

Do not close #461 or mark PR #462 ready from synthetic/API/CI evidence alone. Real installed-game and in-game acceptance remain the draft exit criteria.

## 2026-09-23 misc-bucket review (no agent slice)

- Verified live: PR #462 is MERGED into `master` (`9640d1e0`, merged
  2026-09-23T19:29:01Z, head `2555bc75`). Agent-side packaging/CI is done.
- No code change on `per-game-misc` for this issue. Remaining work is
  Lexer-only: real Steam app 359870 install with Fahrenheit, run
  `run-verifier.ps1` baseline, full-catalog UI smoke, byte-identical EFL
  deploy/startup/revert + Play FFX and Play FFX-2 through Stage 0, one
  reversible structured round trip per game, then verifier compare proving
  both installed VBFs byte-identical. Report `baseline.json`/`after.json`
  plus pass/fail per checklist item on #461.
