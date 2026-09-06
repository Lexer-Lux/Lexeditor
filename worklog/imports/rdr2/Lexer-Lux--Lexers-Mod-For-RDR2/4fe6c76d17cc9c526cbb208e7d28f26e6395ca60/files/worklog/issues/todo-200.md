# Worklog: Todo 200

## #200 exact missing-icon manifest — 2026-08-04

Generated `editor/assets/MISSING_ICONS.txt` by cross-referencing every
`<id>`/`<dict>` pair in `catalog_sp.ymt` against every file under
`editor/assets/inventory_icons` and `editor/assets/item-icons`.

984 missing of 1705 referenced (not "~15%"). By dictionary:
  ITEM_TEXTURES        347 of 347 missing
  UI_ITEMVIEWER        283 of 283
  SATCHEL_TEXTURES     178 of 185
  SWATCHES_GUNSMITH     63 of 63
  SHAVING_MENU          40 of 40
  INVENTORY_ITEMS       24 of 673
  AMMO_TYPES            22 of 22
  MULTIWHEEL_WEAPONS    15 of 62
  INVENTORY_ITEMS_MP     5, ITEMTYPE_TEXTURES 3, WEAPON_TEXTURES_MP001 2,
  INVENTORY_ITEMS_TU 1, SWATCHES_GUNSMITH_MP 1
  LEX_INVENTORY_ITEMS    0 of 11  (our own - confirms that pipeline works)
Five dictionaries cover 911 of the 984, so the OpenIV session should export whole
dictionaries rather than hunting individual textures.

NOTE: `_downloads/rdr3_discoveries/useful_info_from_rpfs/textures/*` contains
README.md NAME LISTS for these dictionaries, not images. Useful for verifying
names, useless for the editor, which needs actual files.

## #200 — "femga does not host these dictionaries" is FALSE, 2026-08-04

The claim that sent this item to OpenIV is wrong. `_downloads/rdr3_discoveries/
useful_info_from_rpfs/textures/*/README.md` are not just name lists: each one
carries femga download links, both a full-pack zip and per-texture PNG URLs.
`inventory_items/README.md` alone contains 1201 image URLs.

Pack URL pattern:
  https://femga.com:8080/images/samples/ui_textures/<dict>.zip          (with bg)
  https://femga.com:8080/images/samples/ui_textures_no_bg/<dict>.zip    (no bg)

Locally documented packs: blips, blips_mp, inventory_items, ui_swatches,
itemtype_textures (under the menu_items folder), feeds, multiwheel_emotes,
overhead, pm_awards_mp, pm_collectors_bag_mp.

Cross-referenced against the missing-icon manifest:
  ITEMTYPE_TEXTURES (3 missing)   -> covered, itemtype_textures.zip
  INVENTORY_ITEMS  (24 missing)   -> covered, inventory_items.zip
  SWATCHES_GUNSMITH (63 missing)  -> probably covered by ui_swatches.zip, verify
  ITEM_TEXTURES (347), UI_ITEMVIEWER (283), SATCHEL_TEXTURES (178),
  SHAVING_MENU (40), AMMO_TYPES (22) -> not in the LOCAL notes, but the URL
  pattern is uniform so they are very likely published too. One HTTP check each
  settles it.

NOT ACTIONED: fetching anything from the internet needs Lexer's explicit yes
first, and he is asleep. The point of this entry is that #200 is probably a
download job, not an OpenIV job — which also means it does not need the game
closed or any GUI driving.

## #200 corrected TWICE — the real gap is 633 in two dictionaries, 2026-08-04

Correction 1: "femga does not host these dictionaries" is false. Its packs and
per-texture PNGs are linked from the reference notes already in the repo.

Correction 2: my own 984 figure was measuring the wrong thing. `inventoryIconUrl`
in `editor/editor.html` ALREADY falls back to
`https://femga.com:8080/images/samples/ui_textures_no_bg/<lowercased dict>/<id>.png`
for any dictionary it has no local copy of. Verified against the reference notes
that femga's URL folder IS the lowercased dictionary name (checked
satchel_textures -> .../satchel_textures/, multiwheel_weapons ->
.../multiwheel_weapons/), so the editor's existing URL construction is correct.
Counting "no local file" therefore counted 351 icons that already render.

Extracted every dictionary femga documents (the `<h2>` headings across all
sixteen texture folders) and cross-referenced against the catalog:

  DICTIONARY              REF  LOCAL  FEMGA  TRUE GAP
  INVENTORY_ITEMS         673    649   yes         0
  ITEM_TEXTURES           347      0    NO       347
  UI_ITEMVIEWER           283      0    NO       283
  SATCHEL_TEXTURES        185      7   yes         0
  SWATCHES_GUNSMITH        63      0   yes         0
  MULTIWHEEL_WEAPONS       62     47   yes         0
  SHAVING_MENU             40      0   yes         0
  AMMO_TYPES               22      0   yes         0
  INVENTORY_ITEMS_TU        7      6    NO         1
  INVENTORY_ITEMS_MP        5      0   yes         0
  ITEMTYPE_TEXTURES         3      0   yes         0
  WEAPON_TEXTURES_MP001     2      0    NO         2
  SWATCHES_GUNSMITH_MP      1      0   yes         0
  Already served by femga: 351.  Genuine gap: 633.

So no downloads are needed at all — the editor is already doing it. The task is
one OpenIV session exporting TWO dictionaries, ITEM_TEXTURES and UI_ITEMVIEWER,
which is 630 of the 633.

