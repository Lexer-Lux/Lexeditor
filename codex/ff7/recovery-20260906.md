# FF7 PR #359 recovery and continuation — 2026-09-06

Continues `fix/ff7-data-and-tweaks-20260906` from `e8b375ff20ffc0855dbd2f9864cabc790ad82d37`, rather than replacing parallel game branches. This note supersedes the earlier FF7 handoff's statement that no scene, shop or kernel2 editor is connected. It does NOT declare the broad #79 acceptance complete.

## Implemented in this continuation

- Enemies: existing English scene definitions, names, stats, rewards, resistance bytes, loot, attacks, animations, camera references and manipulate attacks.
- Enemy attacks: existing attack names and documented numeric attack fields. The undocumented byte at attack offset 3 is preserved.
- Encounters: all 1,024 battle formations, composition, signed positions, cameras and setup fields. This is NOT field/world encounter placement editing.
- Shops/prices: 80 shop inventories and 416 global item/equipment/materia prices. Only explicitly identified English executable builds are writable. Unknown or already-modified installed executables are refused, not guessed.
- Text: all 18 English kernel2 sections, including names/help, battle text and summon attack names. Reversible byte escapes preserve control tokens. The original KERNEL.BIN embedded text remains separate and read-only in the numeric editors.
- Characters: initial equipment, materia IDs and 24-bit AP, gauges, counters, growth-curve selection, recruitment offset, limit attacks and HP divisors, in addition to the earlier starting-stat/limit-learning fields.
- UI/HTTP: independently available source families, actual text inputs, per-family snapshots, search, vanilla inspection/restore, project save/readback and Data Map navigation. A failure in one family does not hide readable families. Partial multi-file saves retain the correct saved/dirty state per file.

## Save contract and boundaries

`scene.bin` is validated as 256 English 7,808-byte scenes in complete 8,192-byte blocks (at most 64 blocks). The writer keeps exactly the original scene-to-block membership, reuses unmodified compressed members, and refuses a changed block that exceeds capacity. Consequently it does not rewrite or invalidate KERNEL's block lookup. Unknown bytes and AI are preserved. Cross-block repacking is not supported.

`kernel2.bin` is parsed as an LZS container around 18 length-prefixed text sections. No-op output is byte-identical. Only changed text sections are rebuilt; invalid escapes, unsupported characters and output exceeding the 27,648-byte game buffer are rejected before a file replacement.

Shop source identity is based on the SHA-1 allowlist documented by Scarlet. The actual 2026 executable candidate is `ff7/resources/ff7_1.02/ff7_en`; the launcher executable is never patched. Legacy candidates are `ff7_en.exe` and `ff7.exe`. Ambiguous installations are refused. Active item/materia references are checked. Only project copies are written, not executable code or installed files.

Extended saves require matching source/active SHA-256 and project-presence snapshots, exact record IDs and fields, bounded values, output readback, an unchanged source at replacement time, and a project outside the installed game directory. Symlink/path escapes and hard links to the source are refused. Existing project data receives a uniquely named backup. This is an atomic replacement per source file, not a cross-file transaction. Saving a project is not automatic deployment to the running game.

Character ranges are storage bounds, not balance recommendations. Existing saves and recruitment scripts can override initial data. Slots 6/7 also serve Young Cloud/Sephiroth; Cait Sith/Vincent initialization in the executable is not edited here. Character AI, growth-curve coefficients, inline character names, scene AI and field/world/script placement remain future work.

## Verification

- `python tools/verify_ff7_datasets.py`: 19 passing local synthetic binary/HTTP tests, including every exposed character field in every slot.
- `python tools/verify_ff7_extended.py`: 15 passing local tests for compression, byte preservation, text controls, documented offsets, invalid references, stale files, backups, unsupported profiles, source isolation and archive overflow.
- Seven browser interaction scenarios cover both kernel editions, independent Tweaks loading, in-flight refresh safety, scene save/reopen, text/shop saves, and partial failure bookkeeping. They use the real editor script and HTTP handler with component contract doubles. CI separates the browser groups so large synthetic scene responses do not share a long-lived test driver with unrelated scenarios.
- No installed-game data, native desktop visual acceptance, deployment or in-game gameplay acceptance was available in the recovery environment. Do not treat synthetic tests as proof of those checks. Keep #79 open until the remaining functionality and product-specific acceptance are complete.

## Primary layout references

The code was implemented from format facts; no game assets or third-party implementation are bundled.

- Battle scenes and KERNEL lookup: https://ff7-mods.github.io/ff7-flat-wiki/FF7/Battle/Battle_Scenes.html
- Attack record offsets: https://ff7-mods.github.io/ff7-flat-wiki/FF7/Attack_data
- KERNEL/kernel2 sections and game buffer: https://ff7-mods.github.io/ff7-flat-wiki/FF7/Kernel/Kernel.bin.html
- Character initialization/growth: https://github.com/Shojy/Elena/blob/d85e02678670763c663cd058463f7578b957912e/Shojy.FF7.Elena/Sections/CharacterData.cs
- Shop layout, executable offsets/identities, and kernel2 length prefixes: `src/ExeEditor/ShopInventory.cs`, `src/ExeEditor/ExeData.cs`, and `src/Compression/Gzip.cs` at https://github.com/petfriendamy/ff7-scarlet/tree/10a228378c0cab4925cbf6f1237a92146a9a719c
