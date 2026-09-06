# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356330248 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286

Created: 2026-08-16T02:21:04Z; updated: 2026-09-05T07:04:53Z

Exact metadata: [source record](sources/issue-5356330248-26807850820d5e1a666e1d0f4afb93ba630f67dbd17da46e02f65096f93638c7.json).

## Goal

Make Red Dead Online content available in Story Mode so it can be tested before any later cut, niche, or balance decisions.

This issue is the live replacement for the old design item **16. CUT AND BULK**. GitHub Lexer-Lux/Lexeditor#116 is already used by Bullet Tracers and must not be changed.

## First milestone

Import RDO content into the existing Story Mode mod in controlled category batches:

- weapons and weapon components
- clothing and wearable equipment
- provisions, tools, kits, and other inventory items
- time-limited and Outlaw Pass items that still exist in the installed game data

For every batch:

1. derive the changes from Rockstar data and independently documented behavior;
2. do not redistribute files from a mod that forbids redistribution;
3. merge into the existing MyOverhaul data instead of installing an unreviewed full-file replacement;
4. provide a clear way to obtain and test each imported item in Story Mode;
5. prove that each item is usable, not only listed in a catalog or inventory.

Do not start the later content cuts or weapon-role rebalance in this milestone.

## Related follow-up work

- Find and enable the Online bucket helmet for armored enemies.
- Make Improved/Refined Binoculars a functional upgrade, not a duplicate or dead wheel item; coordinate with Lexer-Lux/Lexeditor#158.
- Import the intended Outlaw Pass glasses for Bandit rank 4 and find a proven way to reduce the law search radius while worn; coordinate with Lexer-Lux/Lexeditor#148.
- Inventory merge-hostile weapon-overhaul files before any compatibility work.

## Acceptance

A generated inventory identifies every candidate by category and source record. Selected test batches are installed into Story Mode, visibly obtainable through a documented route, and confirmed to function in game. Items that need Online scripts or other unavailable systems are marked as blocked instead of called complete.


## issue 5356330248 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286

Created: 2026-08-16T02:21:04Z; updated: 2026-09-06T12:57:11Z

Exact metadata: [source record](sources/issue-5356330248-68c97b9526864730d43a31213f839750d19be574bf13f7e6a34c54b2f92a1eed.json).

Make imported Online content genuinely usable in Story Mode while preserving existing custom items and effects.

**Status: Partial.** Irish Whiskey and Old Tom Gin work in the satchel, but their missing item-wheel mappings are only prepared, not installed. Deliver those mappings before a retest. Catalog entries alone do not establish complete Online-content support.

## comment 5550163508 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163508

Created: 2026-08-16T02:51:15Z; updated: 2026-08-16T02:51:15Z

Exact metadata: [source record](sources/comment-5550163508-8dcd8fdf755984de549e4b2e50005cc9d86f544031a10ed8db4c530796d23458.json).

Reference pass complete. I inspected OCU 3.0 and RDO 1.3.3 without installing them. OCU mounts Online resources by making 101 named change sets unconditional across 11 Rockstar manifests. RDO then adds Story catalog, shop, weapon, localization, and compendium records; its ASI only supplies six special throwables and keeps four Online texture dictionaries loaded. The generated review inventory contains 19,793 RDO-added catalog records and 1,258 missing records that RDO puts directly in Story shops. I also located the armored helmet asset candidate as `0x676A3198` / `MP_HELMET_MR1_000_FULL` and built a clean manifest generator which preserves current Rockstar records and stops on missing dependencies. No reference files were copied into MyOverhaul, and no files were installed in the game. The independent mount and merge still need the current original Rockstar manifests, followed by runtime item tests.

## comment 5550163533 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163533

Created: 2026-08-16T03:23:18Z; updated: 2026-08-16T03:23:18Z

Exact metadata: [source record](sources/comment-5550163533-d77fed840c576b3ebb24f0699f36c0195f696b6d5b2011cf26056f31c5ecdbbb.json).

The current Rockstar source set is now complete. A read-only RPF8 CLI extracted all 11 manifests; the ten files already extracted through OpenIV matched it byte-for-byte. The independent builder then produced all 11 Story-ready manifests, removed the Online conditions from 62 selected change sets, and verified all 740 known resource memberships. Rockstar had moved one old cross-pack animation reference from MP005 to MP008, so the check now accepts a move only when the current selected manifests still contain and enable that exact resource. Nothing is installed yet. The resource-mount layer is built; the Story catalog and shop merge still remain before the items can be tested in game.

## comment 5550163545 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163545

Created: 2026-08-16T04:00:29Z; updated: 2026-08-16T04:00:29Z

Exact metadata: [source record](sources/comment-5550163545-d8e9e608e30cce16b2d9551ffc3e1c117737075d613a24493fc6dbd7ed00c3d9.json).

The first Story import is installed. MyOverhaul now mounts the current Online resource packs and covers the full RDO catalog, Story shop rows, wearable table, localization, and all 14 weapon-data layers. Existing MyOverhaul catalog item bodies were preserved.

After a full RDR2 restart in Story Mode:

1. At a Gunsmith, check for the Improved Bow, Elephant Rifle, and Reinforced Lasso. Buy each visible item, equip it, and fire or use it.
2. At a General Store, check for the Advanced Camera. Buy it and take one photo.
3. At a Fence, check for the Metal Detector, Collector/Trader/Horror melee weapons, and bolas. Buy and use at least one tool, one melee weapon, and one throwable.
4. At a Tailor or Trapper, buy one added clothing item, wear it, and save the outfit. At a Stable, buy and equip one added saddle or other horse item.

A shop listing alone is not a pass. Report the first item that is absent, cannot be bought, cannot be equipped, or does nothing, plus the store and town. The old RDO ASI is not included, so special throwables are the most likely data-only boundary.

## comment 5550163560 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163560

Created: 2026-08-16T04:31:05Z; updated: 2026-08-16T04:31:05Z

Exact metadata: [source record](sources/comment-5550163560-65967e4eb7bc6b98151fa122d595f36ffc2bdecc6534a7a9daa8dc04531210ce.json).

The missing ASI layer is now installed. GameplayTweaks independently recreates the working RDO loader method: it adds the six special weapon entries with zero ammo, so it does not refill used throwables, and it keeps the four Online texture dictionaries loaded. You do not need the RDO loader.asi. Fully restart RDR2 in Story Mode, then run the store, equip, wear, and use checks from the prior comment. GameplayTweaks.log will also report online-content weapon ownership and texture-load counts. If an item fails, report the first item, the store and town, and whether it was absent, unbuyable, unequippable, or unusable.

## comment 5550163578 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163578

Created: 2026-08-16T05:24:10Z; updated: 2026-08-16T05:24:10Z

Exact metadata: [source record](sources/comment-5550163578-efc145fb71de66a32f29fd06484d92210f38264863c283a1aefa6b7bf51297a0.json).

The first Story runtime test rejected this import. The broad catalog replacement caused a global inventory failure: both wheels were empty, cash read zero, item limits were invalid, and the General Store had no interaction prompt. This is not an item-specific compatibility problem. Lexer-Lux/Lexeditor#286 is back to actionable. I have prepared an exact pre-import data recovery and removed the Lexer-Lux/Lexeditor#286 ASI loader from the recovery build; a watcher will apply and verify both when RDR2 closes. The next test is recovery only: normal Story wheels, cash, and shop interaction must all work before any smaller Online category is imported.

## comment 5550163588 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163588

Created: 2026-08-16T06:01:39Z; updated: 2026-08-16T06:01:39Z

Exact metadata: [source record](sources/comment-5550163588-519f06ec634495514737f46cb253db5e27894d2857734cee303f8256cda57d21.json).

The recovery is now installed and verified. The failed broad catalog/resource import is gone, and the recovery ASI no longer includes the Lexer-Lux/Lexeditor#286 Online loader. Start Story Mode and confirm four base-game controls: the weapon wheel has your weapons, the item wheel has your items, cash shows the correct balance, and a General Store shopkeeper shows the normal interaction prompt. This proves recovery only; Lexer-Lux/Lexeditor#286 remains actionable until the Online content is rebuilt as a bounded import.

## comment 5550163603 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163603

Created: 2026-08-16T07:02:34Z; updated: 2026-08-16T07:02:34Z

Exact metadata: [source record](sources/comment-5550163603-efebb3d4ea11e5689dfff5ba7a604227bed0baa3f5e21ce88bb4f40642f1cfea.json).

The first import used the wrong structure: it appended RDO into MyOverhaul's smaller Story catalog, while RDO 1.3.3 replaces its catalog and shop files as complete units after 11 Online pack manifests are mounted. I rebuilt it from that reference layout. All 24,664 RDO item records remain unchanged, the 42 MyOverhaul-only items are added on top, and the exact RDO shop, compendium, and non-colliding weapon files are mapped. RDO's loader behavior is recreated in GameplayTweaks rather than copying loader.asi. The next complete restart must confirm ordinary wheels and shops first, then one RDO weapon and one RDO clothing item.

## comment 5550163614 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163614

Created: 2026-08-16T07:05:02Z; updated: 2026-08-16T07:05:02Z

Exact metadata: [source record](sources/comment-5550163614-fe27b49ef3b8de93996601e87d96d8ad6eee0e0b280298ff023c2b79f7a34703.json).

Follow-up phase after the reference RDO build passes its Story test: compare the complete Online-content inventory against what RDO actually registers and exposes. Produce a review list of Online items RDO omits, grouped by weapons, clothing, equipment/items, horses, and support-only records. Then decide which omitted player-usable items to add. Do not assume RDO represents all Online content, and do not add missing records until the known-working RDO baseline is confirmed.

## comment 5550163622 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163622

Created: 2026-08-16T07:23:05Z; updated: 2026-08-16T07:23:05Z

Exact metadata: [source record](sources/comment-5550163622-2f6168ba08a75d92db9f8e98a20cb4142df0d153fe2f1d859f69294975b167e5.json).

Partial in-game pass: the Online metal helmet component 

## comment 5550163634 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163634

Created: 2026-08-16T07:27:05Z; updated: 2026-08-16T07:27:05Z

Exact metadata: [source record](sources/comment-5550163634-8beb74e0c5cb997c27d73aa0f47f070634b8beaaf76f6361ad81ddadd9d36aa8.json).

Hidden-wearable audit after the helmet pass: RDO mounts 6,890 multiplayer-origin male Story components, but only 542 are directly stocked or awarded. The other 6,348 variants represent about 841 drawable models. Of those, 4,285 already have catalog prices but no shop stock row, 1,734 are support-only catalog records, and 329 have no catalog record and need direct component handling like the helmet. Large hidden groups include 924 hat variants, 624 boots, 744 open/closed coats, 493 pants, 480 shirts, 284 vests, 104 masks, 86 eyewear pieces, 35 poncho/cloak entries, 16 gauntlets, 10 armor variants, 3 badges, and 3 satchels. Many are tints or outfit internals, so each drawable still needs a fit/clip test before it becomes normal player content.

## comment 5550163647 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163647

Created: 2026-08-16T08:09:22Z; updated: 2026-08-16T08:09:22Z

Exact metadata: [source record](sources/comment-5550163647-2d267b5f665fa3192f97bc6a98abd09a9b05b8a16fb0e4c7d9dc60888bc90d02.json).

LEXEDITOR now opens the exact RDO catalog named by `install.xml` instead of the inactive root copy. A leading `★` marks RDO-added records in Items, Crafting item links, Effects, Shops, and Weapons. The Weapons page now includes every active weapon layer and saves an edit back to that record's exact layer.

Visual check: restart LEXEDITOR, open Items, and search for `WEAPON_BOW_IMPROVED`; its name must start with `★`. In Weapons, Improved Bow, Navy, and Elephant must be starred, while Cattleman must not be. Search, sorting, and saved IDs must remain unstarred internally.

Component-only wearables that have no catalog record are still outside these normal tabs. They need a separate clothing/component inventory; the catalog star cannot make them appear.

## comment 5550163662 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163662

Created: 2026-08-16T10:22:39Z; updated: 2026-08-16T10:22:39Z

Exact metadata: [source record](sources/comment-5550163662-354878776c69c49f35d96c704e10ccf8092f43150af80ba2d3a0deea9629fbb0.json).

The active replacement catalog kept the Online records but ignored edits on shared Story records, which is why custom prices reverted. I am rebuilding one authoritative root catalog that preserves the original item records, shop membership, effects, layouts, and Online-only additions; the staged duplicate catalog will be removed.

## comment 5550163683 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163683

Created: 2026-08-16T10:48:09Z; updated: 2026-08-16T10:48:09Z

Exact metadata: [source record](sources/comment-5550163683-6b5829110d56c33e4c34415f5aa8d3287039238478cbfd5b1c8955e95105af1c.json).

The recovery is installed through the live MyOverhaul junction. Story and LEXEDITOR now use the single root catalog; the duplicate deploy catalog is gone. The merge preserves the original item records, prices, shop membership and requirements, effects, categories, layouts, outfit bundles, paths, and path sets while retaining all Online-only records. On one full Story restart, confirm: weapon and item wheels are populated; cash is normal; a shop prompt appears and the shop opens; the Cattleman costs $17.80; the equipped mask appears in its radial slot; and the metal helmet plus another Online-only item still work.

## comment 5550163693 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163693

Created: 2026-08-16T11:00:24Z; updated: 2026-08-16T11:00:24Z

Exact metadata: [source record](sources/comment-5550163693-ab2f63e177fe5cba4ac77cb7e8379a86884e27f9330b9f2602122c5c2eed4d71.json).

LEXEDITOR needs separate origin markers: one for records imported from Red Dead Online and one for locally created catalog records, including the 42 existing records absent from both Vanilla and the RDO source. The marker must remain display-only and follow linked items across Items, Crafting, Shops, and other relevant lists.

## comment 5550163708 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163708

Created: 2026-08-16T11:32:44Z; updated: 2026-08-16T11:32:44Z

Exact metadata: [source record](sources/comment-5550163708-cd21018de8754a9d599eaf116431e0b5c5fd825a1b689046488f183b9bc2807e.json).

LEXEDITOR now uses two display-only origin icons instead of the star: a steel-blue globe for Red Dead Online records and a brass pen nib for locally created records. All 42 existing local-only items are seeded, including older non-LEX brass provisions, and future items or effects created in LEXEDITOR register their custom origin automatically. To check it, open Items and compare Improved Bow (globe), Gunpowder or Ring Brass (pen nib), and Cattleman (no icon); hover each icon for its origin text.

## comment 5550163722 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163722

Created: 2026-08-17T03:42:59Z; updated: 2026-08-17T04:37:21Z

Exact metadata: [source record](sources/comment-5550163722-fa7e26dcd651bf133192a70aeea0109aed0e933ca9c1f4a323144ef0101394b6.json).

The page-layout retest failed, so that cause claim remains withdrawn. The live sequence proved a pre-UI shop abort: the doctor took ownership, disabled control, never opened a catalogue or item list, and restarted from thread 75 to 81 without cleanup.

The catalogue merge had also put too many entries on 19 declared-capacity pages, including three doctor grid-of-four pages with five entries. The corrected merge splits only the excess entries into reachable pages. It preserves all 5,096 user records, all 19,610 Online-only records, and the intentional doctor Navy stock row and page.

A one-shot recovery is also installed. It restores Rockstar's abandoned shop state only when the doctor thread changes while control is off and no shop, inventory, satchel, crafting, pause, item-list, or item-interaction state exists. Alt-Tab alone cannot trigger it.

This is installed but not yet confirmed in game. Start Story fresh, open the doctor catalogue, confirm the Navy Revolver is present, then close it and confirm movement and prompts return. If the catalogue still aborts, the recovery should restore control and log a delayed readback.

## comment 5550163745 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163745

Created: 2026-08-17T03:49:48Z; updated: 2026-08-17T03:49:48Z

Exact metadata: [source record](sources/comment-5550163745-b124b5ef0128e026679398d973e2bd25b8eb39468784ac5433decf2dc1175c7c.json).

The local-origin nib in the screenshot was a custom monochrome SVG, not an emoji font fallback. It is now a real color `✒️` glyph, and only that marker is forced through `Segoe UI Emoji`. The Online globe and every shared utility font remain unchanged.

The RDR2 render confirmed a visible 16-pixel emoji, no CSS fallback mask, the original globe unchanged, no browser errors, and no catalog or provenance change. Fully close and reopen Lexeditor to load the updated page.


## comment 5550163755 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163755

Created: 2026-08-17T04:18:16Z; updated: 2026-08-17T04:18:16Z

Exact metadata: [source record](sources/comment-5550163755-1b9e41bc84dfaa95d434eca9e3a2d969e5b4c3b704b1f160748fad851c0dcf52.json).

Runtime result: `CONSUMABLE_IRISH_WHISKEY` and `CONSUMABLE_OLDTOM_GIN` both appear in the satchel and can be consumed there, but neither appears on the item wheel.

These paths use separate data. Both records are `CI_CATEGORY_COLLECTIBLE` / `CONSUMABLE` and carry `CI_TAG_FOLDER_COLLECTOR_BOTTLES`, whose tag type is the satchel-folder family. Ordinary whiskey also has an explicit `quickselectitems.ymt` mapping to `PLAYER_PROVISIONS`; these two records have no entry in the active Story quick-select file. The mounted MP005 layer is locked while RDR2 is running, so this pass did not prove whether that layer supplies a mapping that Story later rejects. The in-game result proves that there is no effective Story radial entry.

The blank LEXEDITOR names are a separate editor lookup gap. Both catalog records contain a primary UI key plus hashed `LABEL_TYPE_ALT_NAME` and `LABEL_TYPE_ALT_DESC` entries. The game resolves the Online text, but LEXEDITOR currently reads only the primary UI key from its Story localization snapshot plus `strings.gxt2`; neither source contains these keys, and the editor does not fall back to the alternate localization entries. Blank editor text therefore does not mean that the game record has no name. The correct repair is to add Online localization coverage and alternate-key resolution, not to hand-fill catalog names.

## comment 5550163764 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163764

Created: 2026-08-17T04:21:19Z; updated: 2026-08-17T04:21:19Z

Exact metadata: [source record](sources/comment-5550163764-3aff64c71ee0bf9de3e3f920a46b04a72970558b38c5eac7923c79f5bac82b6a.json).

Saving the new doctor stock entry through the already-open LEXEDITOR session rewrote the root catalog from its stale cached copy and reinstated the rejected 51.5 MB expanded catalog. The new stock and page records are preserved for recovery, but the root catalog must return to the known-good version and LEXEDITOR must reject stale whole-file saves before this test continues.

## comment 5550163783 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163783

Created: 2026-08-20T06:20:08Z; updated: 2026-08-20T06:20:08Z

Exact metadata: [source record](sources/comment-5550163783-28a229ed7b65ba11b31e9ca0c5f92b737bef063fd959c772bcd97e2c4cd2332a.json).

Correction: the 16 MB catalogue is only the customized pre-RDO recovery baseline. It is not the target and must not replace the repaired combined catalogue. The active combined catalogue keeps all 5,096 customized Story records and all 19,610 Online-only records, and its over-capacity pages are now split into valid reachable pages. Lexer confirms that the doctor catalogue now works in game. All further catalogue and Online-content work will continue from this repaired combined file.

## comment 5550163793 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163793

Created: 2026-08-20T07:38:06Z; updated: 2026-08-20T07:38:06Z

Exact metadata: [source record](sources/comment-5550163793-7aaa45002f2892f6c8cb0aa915f0e5a6f70e01ef4d921e23d5ab4038a275ef28.json).

Current 1491.50 base and MP quick-select data contain no item-wheel mapping for `CONSUMABLE_IRISH_WHISKEY` or `CONSUMABLE_OLDTOM_GIN`. That is why both work in the satchel but are absent from the wheel.

I added each item once to `PLAYER_PROVISIONS` and kept all 1,865 existing quick-select entries unchanged. The focused check rejects a missing item, a wrong slot, or any changed existing entry. The data change is not installed.

After installation and a full restart, both bottles must appear on the item wheel, select normally, consume normally, and leave the existing satchel and provision controls intact.

## comment 5550163806 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/286#issuecomment-5550163806

Created: 2026-08-20T08:28:54Z; updated: 2026-08-20T08:28:54Z

Exact metadata: [source record](sources/comment-5550163806-49251b027dd1822a17208c1a3f7ce627fa0979099e55d60ea08b56b2fccbbb62.json).

The combined catalogue preservation check is repaired and passes. It confirms all 5,096 customized Story records, all 19,610 Online-only records, and all 416 effect records. The only unrelated data error was one weapon-grip engraving tag attached to pistol express ammunition; I removed only that tag. The intended doctor Navy stock and reachable page remain intact.

The two missing wheel mappings also pass their focused check: Irish Whiskey and Old Tom Gin each appear once in PLAYER_PROVISIONS, with all 1,865 prior quick-select entries unchanged.

After the next install and a full restart, both bottles must appear on the item wheel, select and consume normally, and leave the existing satchel and provision controls intact.
