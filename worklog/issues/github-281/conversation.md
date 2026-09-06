# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356328685 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/281

Created: 2026-08-13T02:03:19Z; updated: 2026-09-05T07:04:35Z

Exact metadata: [source record](sources/issue-5356328685-e91988324699b820fec5fc841555cb1164db66b0acd3cd986281f30aa1c66785.json).

A maintenance pass deleted several gitignored cache trees (see `fuckups.txt` entry 20). Most of it was re-fetchable, but the extracted game assets were not, because they come from the local game install rather than a public source.

## Why this needs a human

Extraction requires the game archives and OpenIV. Per `codex/archive-extraction.md`, `Rpf8Extract` **cannot** read inside nested encrypted archives — it resolves only top-level hashed entries, and every build throws in `RPF8.Load` on the encrypted blob. So this can't be automated with the tooling in the repo.

## Needs re-extracting

- `quickselectmenus_ymt.xml` — cited as primary evidence in Lexer-Lux/Lexeditor#243's worklog for how the weapon wheel picks its single-wield vs dual-wield provider (`CAIConditionIsDualWieldAvailable` / `CAIConditionIsDualWieldUnlocked`).
- `sub_slot_list.ymt.rbf.xml` — cited in Lexer-Lux/Lexeditor#243 for the ammo-option stepper binding to `INPUT_QUICK_SELECT_SECONDARY_NAV_NEXT/PREV`.
- `_downloads/extract/update_2-keys.tsv` — the index recording which nested archives are encrypted. Referenced directly by `codex/archive-extraction.md`; without it that doc's encryption claims can't be re-checked.

## What is NOT needed (verified, so nobody redoes it)

- **All of `_downloads/` is intact** and every subdirectory is a public GitHub clone (decompiled scripts, SDK, RPF8_TOOL, rdr3_discoveries, etc.), so it is re-fetchable by definition.
- **Build chain works** — `build.bat` returns EXIT=0.
- **MyOverhaul data intact**, 55 entries matching the installed game-root copy.
- **Git intact** — 23 tracked files under `outputs/**/node_modules/` were deleted and have already been restored.
- The extractor survives at `_downloads/RPF8_TOOL/` and a copy at `_analysis/Rpf8ExtractCurrent.exe`.

## Not urgent

Nothing open is blocked on these. They matter when Lexer-Lux/Lexeditor#243's LOADOUT_3 addressing needs re-verifying — which is likely, since its `default=` global still reads `0x3f800000` (the float `1.0f`) rather than a clothing hash after two attempted corrections.

## Worth doing at the same time

`_analysis/` holds every extraction and has no backup anywhere. It cannot go on GitHub — it is Rockstar's data, and `.gitignore` marks this class "never ship or commit" / "do not redistribute". A local copy on another drive is the only thing that would have prevented this.

Note: `Rpf8Extract` prints `Distroy File: <path>` after a **successful** extraction. It is a misspelled handle-close message, not damage. Per the doc it has caused a panic more than once.

## issue 5356328685 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/281

Created: 2026-08-13T02:03:19Z; updated: 2026-09-06T13:18:42Z

Exact metadata: [source record](sources/issue-5356328685-61e349c474744a2704f7c167222e376dfebea0d3daace580a4600cee6feb5a2f.json).

**Status: Original recovery closed; a later gap was reported.** Quick-select/radial evidence and its saved index were restored and backed up. A subsequent audit found ten other missing inputs affecting fourteen checks; no later resolution of that expanded set is recorded here. Do not call every verifier restored.

## comment 5550161938 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/281#issuecomment-5550161938

Created: 2026-08-13T02:44:19Z; updated: 2026-08-13T02:44:19Z

Exact metadata: [source record](sources/comment-5550161938-b275cad29a498e1860ea5acf6225dc515db90c6d2e0589995dfaaa3155375362.json).

Recovered the deleted extraction evidence. I exported the current quick-select provider and radial sub-slot metadata from `update_4` with OpenIV, restored the four-record encrypted update index from its surviving copy, and kept a second copy on `D:`. The provider file contains both dual-wield conditions, the radial file contains both secondary navigation actions, and the Lexer-Lux/Lexeditor#243 verifier passes again.

## comment 5550161971 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/281#issuecomment-5550161971

Created: 2026-08-14T00:45:02Z; updated: 2026-08-14T00:45:02Z

Exact metadata: [source record](sources/comment-5550161971-53ee90192bad014ef2077b6425fd90948e10099adfc0c8da290782b0fd77e5c7.json).

**Commenting rather than reopening — this is yours to decide, but the closure looks premature and I have the exact scope now.**

Working through today's actionables I hit missing-file crashes in verifier after verifier, so I swept all of them. **14 verifiers cannot execute at all.** They do not fail — they throw `FileNotFoundError` and protect nothing:

```
verify_belt_lantern_issue_5              verify_dodge_roll_issue_179
verify_binocular_mask_issue_143          verify_horse_needs_issue_91
verify_campfire_icons_issue_12           verify_pocketwatch_rework_issue_147
verify_dodge_roll_issue_6                verify_prone_issue_9
verify_dodge_roll_issue_172              verify_recon_animal_diamonds_issue_86
verify_dodge_roll_issue_173              verify_recon_plants_issue_96
verify_wagon_stamina_issue_3             verify_water_pumps_issue_89
```

The 10 distinct inputs they need:

```
_analysis/reference-decompilation/Dive-Crawl-N-Gun.c
_downloads/NativeMenuBase/RDR2-Native-Menu-Base-master/inc/natives.h
_downloads/combat-roll-reference/extracted/CombatRoll.asi
_downloads/inspect/hardcore-stamina/Y_Hardcore_Stamina.asi
_downloads/extract/common_0_data/ai/looting/lootable_herbs.meta
_downloads/extract/localization/update_txt/blipdata_ymt.xml
_downloads/extract/radial_ammo_ui/quickselectitems_ymt.xml
_downloads/extract/update_1_common/common/data/ai/scenarios/mech.meta
_downloads/extract/update_1_common/common/packs/base/data/ai/weaponcomponents.meta
editor/assets/item-icons/build_casing_inventory_mp/dds/lex_blip_campfire_inactive.dds
```

Why it matters right now: several of these guard issues that are actively being worked. `verify_prone_issue_9` and the four dodge-roll verifiers cover the movement code I changed today for Lexer-Lux/Lexeditor#104 and Lexer-Lux/Lexeditor#283, and `verify_belt_lantern_issue_5` covers the module I changed for Lexer-Lux/Lexeditor#282. I shipped those changes with those checks unable to run, which I have said plainly on each issue — but it means a regression in that code would currently pass silently.

Not everything here is equally recoverable. The two `.asi` files and the `.c` decompilation are third-party reference material. The `extract/` paths are extractions from your own install, so they can be re-made with the game closed. `quickselectmenus_ymt.xml` has already come back at some point, so part of this set has been restored piecemeal already.

I have **not** reopened this. Whether that is one re-extraction job or several separate ones is your call, and reopening a closed issue on my own judgement is exactly the thing I am not going to do.

