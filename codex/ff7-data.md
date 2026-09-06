# FF7 data editors and verification

Updated 2026-09-06 for the completion pass on PR #359. This is the current scope reference; the earlier `ff7-recovery-20260906.md` is a historical session record, not the current list of missing editors. Both `ff7` and `ff7-2013` use `games.ff7.server` and the same page. No other game's implementation is changed by this pass.

## Connected editors

There are 24 dataset categories, grouped into ordinary tabs and related subtabs, plus Tweaks / FFNx. Missing or unsupported installed data is reported explicitly, independently of other readable categories.

- Kernel: items, weapons, armor, accessories, materia; nine initial character slots with 93 numeric fields; nine inline names; 64 growth curves; three growth-bonus tables; twelve character AI owners.
- Battle scenes: enemy stats, names, rewards, resistances, loot and action references; enemy attacks; all 1,024 formations and cameras; enemy and formation AI scripts.
- Field encounters: both random-encounter tables of each readable PC field in flevel.lgp. Normal and special battle IDs, probabilities, activation and rate are writable. Malformed members are reported and left unchanged.
- World encounters: 64 region/terrain tables, eight Yuffie level thresholds and 32 Chocobo ratings in enc_w.bin inside world_us.lgp.
- Recognized English executables: 80 shops, 416 purchase prices, ten default names, and Cait Sith/Vincent's separate initial records including equipment and materia/AP.
- Text: all 18 English kernel2 sections, with reversible game-byte escapes and an encoded-buffer limit.

Characters, Enemies, Encounters and Shops use subtabs instead of placing every dataset in the main navigation. Real shared-control tests cover textarea initialization, save/reopen, list sizing, both edition identities and three window sizes. Text values must be assigned to textarea.value: setting only the value attribute leaves a real shared textarea blank. Name/description cells use fitted wrappers, avoiding max-content overflow. Selection and subtab sounds are emitted once; muting stops and suppresses playback.

## Binary contracts

Character layout follows Elena d85e026: section 4 has nine 132-byte initial slots; section 3 has nine 56-byte growth/limit records. Bonus tables start at 0x1F8, the 64 sixteen-byte curves at 0x21C, and the 2048-byte character AI pool at 0x61C. Curve gradients are unsigned bytes and bases are signed bytes. Slots 6/7 can represent Young Cloud/Sephiroth; the executable contains distinct Cait Sith/Vincent initialization. Initial data does not rewrite saves and recruitment scripts can override it.

AI uses game-VM assembly, not host-language evaluation. Named instructions have bounded operands; script-local labels resolve jumps. Missing END, trailing instructions, malformed text, bad pointers and jumps into operands/outside the script are rejected. Same-size/shorter scripts preserve surrounding bytes. Growing or aliased owners are copied into known trailing FF slack and their owner/event pointers updated. The fixed pool size is retained; there is no implicit compaction or guarantee of available growth capacity. Byte validation is not a gameplay-logic verifier.

Scenes remain 256 English 7808-byte records in 8192-byte blocks. Original scene-to-block membership is retained, avoiding a stale KERNEL lookup. A block that no longer fits is refused; cross-block repacking is not implemented. Unchanged compressed members and unknown bytes remain preserved.

LGP editing retains lookup/conflict tables, other members and inactive bytes. A resized/aliased member is appended before the footer and its TOC pointer updated, as allowed by the documented format. Field editing touches only section 7's two 24-byte encounter tables. World enc_w.bin remains 2208 bytes. IDs and weights are separated from their packed representation. An enabled zero encounter rate and invalid normal probability totals are refused.

This is encounter-table editing, not a general field-script, world-geometry or executable terrain-assignment editor. Shop-opening scripts and scene enemy IDs remain separate, preserved data. Unknown executable hashes are not accepted at guessed offsets; the production allowlist has no synthetic-fixture bypass.

## Save contract

All binary saves require source SHA-256, active SHA-256 and the usingProject snapshot, exact readable categories, unique record IDs and exact typed fields. Old smoke checks now use the same payload contract. Case-insensitive source resolution rejects ambiguous aliases. Corrupt, directory and broken-link projects do not silently fall back to vanilla.

Projects must be outside the game directory. Target checks reject escaping paths, symlinks and source hard links. Output is staged, decoded again and verified before replacement. Unique exclusive backups avoid following an old backup symlink. Source/project snapshots are checked again before replacement. Each file is replaced atomically; this is not a cross-file transaction. The page records successful families immediately and retains failed families as dirty. AI readback is compared by encoded instructions, allowing canonical formatting on reload.

Binary saves do not deploy mods or alter installed sources. FFNx retains its separate backed-up in-place configuration writer, FF7-only filtering, stale-snapshot and running-game protection. Process names include the current launcher, FFVII.exe and legacy engine identities. Unsaved configuration survives asynchronous refreshes. FF7 Launch sound remains explicitly unavailable rather than using a guessed substitute.

## Repeatable tests

Local results before publication: 57 binary/HTTP tests (19 kernel, 15 extended, 23 completion), seven component-contract browser scenarios, and three real-shared-UI scenarios. The character sweep includes 837 field/slot combinations. New tests cover AI relocation/aliases, LGP append preservation, field/world tables, names/recruits/curves, malformed data, typed no-op validation, snapshots, backups, template guards and diagnostic source preservation. The workflow repeats binary tests on Windows and Linux and browser tests in Chromium. Check the PR's actual current CI conclusions rather than treating this local record as a CI result.

## Installed-data check and remaining acceptance

Run `tools\FF7-checks.cmd` from a normal Lexeditor checkout. It uses saved/default FF7 installation paths, or accepts `--game "path"` (repeat for both editions). It reads installed files, writes only a disposable temporary project, verifies no-op binary readback, hashes the installed sources before/after, and writes a JSON report outside the game directories. Missing/unreadable datasets remain errors; a partial check does not report full success. No game launch, deployment or upload occurs.

Actual installed-build compatibility, native desktop behavior, gameplay acceptance of deployed edits and the user's judgment of sound selection remain unverified by the synthetic suite. These checks must not be marked passed by inference. #73 includes other games and #72 includes listening acceptance; an FF7 implementation does not close their unrelated portions.

## Primary format references

- https://github.com/Shojy/Elena/tree/d85e02678670763c663cd058463f7578b957912e/Shojy.FF7.Elena — CharacterData, BattleAndGrowthData and StatCurve.
- https://github.com/petfriendamy/ff7-scarlet/tree/10a228378c0cab4925cbf6f1237a92146a9a719c — AIContainer, Script, ExeData, ShopInventory and compression container layouts.
- https://ff7-mods.github.io/ff7-flat-wiki/FF7/Battle/Battle_Scenes.html
- https://ff7-mods.github.io/ff7-flat-wiki/FF7/Battle/Battle_Scenes/Battle_Script
- https://ff7-mods.github.io/ff7-flat-wiki/FF7/LGP_format.html — Ficedula's LGP documentation, including appended replacement members.
- https://ff7-mods.github.io/ff7-flat-wiki/FF7/Field/Encounter.html
- https://wiki.ffrtt.ru/index.php/FF7/WorldMap_Module/Encounters

Implementation uses format facts; no third-party implementation or game assets are bundled by this pass.
