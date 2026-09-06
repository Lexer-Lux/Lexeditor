# GitHub #11 — Missing Inventory Icons

## 2026-08-05 implementation pass

The editor preview and Story Mode use different sources. LEXEDITOR loaded the
loose PNGs under `editor/assets/item-icons`; the game resolved each catalog
texture from the named YTD dictionary, and the scripted acquisition feed named
its own dictionary and texture independently.

The `.225 Round (AP)` record (`AMMO_PISTOL_EXPRESS`) had no `INVENTORY` texture.
Commit history showed that the vanilla `AMMO_BULLET_EXPRESS` entry was deleted
while the temporary `LEX_AMMO_225` assignment was reverted. Its surviving
`AMMO_TYPES/BULLET_EXPRESS` and `ITEM_TEXTURES/UI_AMMO_PISTOL_EXPRESS` entries
serve other UI contexts and could not supply the satchel/acquisition icon. The
vanilla `INVENTORY_ITEMS/AMMO_BULLET_EXPRESS` entry was restored.

The empty bottle catalog record was already corrected before this pass: it uses
Rockstar's `INVENTORY_ITEMS/GENERIC_BOTTLE`, not the rejected
`LEX_ICON_EMPTY_BOTTLE` artwork. No replacement bottle art was assigned.
Integration changed all four manual empty-bottle `CASING_FEED` calls to
`INVENTORY_ITEMS/GENERIC_BOTTLE`, so scripted bottle pickup cards match the
catalog. It also made casing feed cards select the same dictionary as their
catalog record: `.22` and shotgun use Rockstar's resident dictionary while the
three centerfire drawings use `LEX_INVENTORY_ITEMS`.

The six casing catalog records had drifted to six per-family custom texture IDs,
while the approved design and the scripted pickup feed use three caliber icons:
`.225`, `.307`, and `.444`. The catalog now uses `LEX_CASING_225` for pistol,
`LEX_CASING_307` for revolver, and `LEX_CASING_444` for repeater and rifle.
Varmint casing and shotgun hull now use the shipped `AMMO_RIFLE` and
`AMMO_SHOTGUN` inventory textures respectively; custom art remains limited to
the three requested centerfire calibers.

Static evidence:

- `LEX_INVENTORY_ITEMS.ytd` parsed as one dictionary with all three caliber
  texture names present.
- The latest `vfs.log` found, queued, and registered
  `lex_inventory_items.ytd`; registration rather than file discovery was not
  the remaining catalog defect.
- Catalog XML parsed successfully and an audit confirmed exactly one
  `INVENTORY` texture on `.225 AP` and every casing/bottle record.
- Loaded `AMMO_*` records have no `LEX_INVENTORY_ITEMS` inventory textures.

Runtime acceptance after integration/build/install and a full game restart:

1. Open the satchel and verify `.225 Round (AP)` shows the vanilla express-ammo
   icon.
2. Verify Empty Bottle shows Rockstar's vanilla bottle icon in the satchel and
   in the scripted pickup/acquisition card.
3. Pick up pistol, revolver, repeater, rifle, varmint, and shotgun remains;
   verify `.225/.307/.444` use the three related custom casing drawings, while
   `.22` and the shotgun hull use visible vanilla icons.
4. Verify the same icons in the satchel, pickup card, and any crafting ingredient
   list; no blank square may remain.

## Integration

GameplayTweaks built successfully and the ASI, INI, and linked MyOverhaul
catalog were installed with matching hashes. ASI SHA-256:
`7E414A0625EC216CDD7147ADABEC6BFE7E7452EBCA95C42CE66FFCB2689E654A`.
Catalog SHA-256:
`F319E7C0F275A6AB812051D26E7B32506CE187C7D20201FAA3091559214B3B82`.

## 2026-08-06 follow-up after in-game report

Lexer confirmed that `.225 Round (AP)` was fixed, but casing records remained
blank and native casing pickups produced no acquisition card. The shotgun hull
was the exception only because the prior pass had replaced its custom art with
Rockstar's generic shotgun-ammo icon; that was not the requested hull artwork.

Current deployment evidence ruled out a stale or misplaced texture archive:

- `vfs.log` registered `addonDLC:/stream/lex_inventory_items.ytd`.
- The source, repo-streamed, and live game-root copies of
  `LEX_INVENTORY_ITEMS.ytd` were byte-identical, SHA-256
  `C170BB1C824DE7348709E541B83C97CC5C979EBB0081CD84E4791E899306EBE6`.
- The live INI selected `PickupMode=native`.
- The current casing log contained only module registration, so it did not yet
  prove whether Story Mode considered the custom texture dictionary existent or
  loaded.

The missing acquisition card had a direct code cause. The animated/manual
pickup path called `CASING_FEED`, but the active native-pickup path erased the
collected pickup immediately after `HAS_PICKUP_BEEN_COLLECTED` and never posted
a feed card. The native branch now posts the same per-item card exactly once
before erasing the pickup, and logs the dictionary and texture used.

The shotgun record and scripted feed were restored to the already-shipped
`LEX_INVENTORY_ITEMS/LEX_CASING_SHOTGUN` hull artwork. Varmint remains on the
visible vanilla rifle-ammo fallback; the centerfire families retain the three
caliber drawings from the prior pass.

Because LML registration alone does not prove the game can stream an arbitrary
dictionary, the casing module now logs one runtime probe for
`LEX_INVENTORY_ITEMS`: `_DOES_STREAMED_TEXTURE_DICT_EXIST` plus whether it was
already loaded before the request. This is diagnostic evidence, not a claim
that requesting the dictionary fixes catalog UI.

Integration boundary: source and catalog changes are ready for the integration
agent. This worktree did not build, install, edit the dispatcher, change GitHub
labels, commit, or push.

Runtime acceptance after integration/build/install and a full restart:

1. Fire and collect one casing in native mode; an acquisition card must appear.
2. Confirm `GameplayTweaks.casings.log` contains the native collection line with
   `feed_dict`/`feed_icon`, plus the one-time custom-dictionary probe.
3. Check pistol, revolver, repeater/rifle, and shotgun-hull custom icons in both
   acquisition cards and the satchel. Record whether the probe says `exists=1`;
   if icons are still blank, that result determines the next fix rather than
   another archive rebuild.

## 2026-08-06 returned-test fix: use an existing loadable dictionary

The returned test proved every custom casing icon was still blank, including
the shotgun hull. The live `GameplayTweaks.casings.log` supplied the decisive
result: `LEX_INVENTORY_ITEMS exists=1 loaded_before_request=0`. The companion
map-icon log repeatedly showed the same condition for another newly named YTD.
LML had registered the file, but Story Mode never completed the streamed
request. Rebuilding or requesting that same new dictionary again was therefore
not a fix.

The casing art now lives in a complete replacement of Rockstar's existing
`INVENTORY_ITEMS_MP` dictionary. Its build preserves all 432 original MP
textures and adds exactly `LEX_CASING_225`, `LEX_CASING_307`,
`LEX_CASING_444`, and `LEX_CASING_SHOTGUN`. Because the resource name already
exists in the game, the LML streaming replacement can actually load; preserving
the complete source set avoids blanking unrelated MP inventory icons.

Catalog mappings and acquisition cards now use `INVENTORY_ITEMS_MP` for the
four approved custom drawings. Varmint remains on Rockstar's visible
`INVENTORY_ITEMS/AMMO_RIFLE` fallback, and Empty Bottle remains on
`INVENTORY_ITEMS/GENERIC_BOTTLE` as confirmed working. The merged RDR2 YTD is
`MyOverhaul/stream/inventory_items_mp.ytd` (436 textures, RSC8).

Static checks passed:

- `python tools/reverse-engineering/verify_inventory_icons_issue_11.py`
- the asset build reported 432 Rockstar textures plus four custom textures;
- catalog XML parsed successfully; and
- the resulting YTD has an RSC8 header and is 2,933,212 bytes.

Integration must copy the stream asset to the normal LML stream destination,
then build/install the ASI so acquisition cards request the same resident
dictionary. Runtime acceptance remains: the four custom drawings must render
in both satchel/crafting UI and acquisition cards; `.225 AP`, Empty Bottle, and
varmint must retain their already-working resident icons.

## 2026-08-06 second returned-test fix: use Story's resident dictionary

Lexer restarted with the complete `INVENTORY_ITEMS_MP` replacement installed
and reported no visible change. The live module log showed Story Mode recognized
the MP dictionary name but did not have it loaded. Treating an Online resource
name as a reliable Story inventory resource was therefore the wrong assumption.

An attempted complete `INVENTORY_ITEMS` build was rejected before installation:
its 803 textures exceeded the current RDR2 converter's non-relocating resource
page limit. Shipping a partial replacement would blank unrelated Story icons,
so that unsafe fallback was not used.

The custom casing drawings instead extend `GENERIC_TEXTURES`, a 45-texture
dictionary used directly by Story shop scripts. Its complete vanilla source is
preserved, and the four approved casing drawings are added to it. Catalog
records and acquisition cards now name that same dictionary, which the ASI
requests before collection. The unrelated MP replacement was not deleted
because other unfinished work currently references it.

Runtime acceptance remains unchanged and requires a full restart because both
the catalog and YTD are startup-loaded.

## 2026-08-07 root cause found: uppercase texture names are filed under a hash the game never computes

Every prior pass assumed the defect was *which dictionary* the art lived in, and
rebuilt it three times (`LEX_INVENTORY_ITEMS`, then `INVENTORY_ITEMS_MP`, then
`GENERIC_TEXTURES`). All three produced the same blank icons because none of
them was the problem. The dictionary choice was already correct on the third
attempt, and the live log proves it:

    GameplayTweaks.casings.log:2
    texture dictionary GENERIC_TEXTURES exists=1 loaded_before_request=1

The dictionary existed, was resident, and was byte-identical between repo and
game root. The textures were inside it. The lookup still missed.

A RAGE texture dictionary is a `pgDictionary` keyed by the **joaat hash of the
texture name**, and every consumer lowercases the string before hashing. That is
directly observable in shipped data, not inferred: all 1661 real `<id>` values in
`MyOverhaul/catalog_sp.ymt` are UPPERCASE (`AMMO_RIFLE`, `GENERIC_BOTTLE`), while
every texture name inside every shipped Rockstar `.ytd` is lowercase
(`ammo_rifle`, `medal_gold`). Those two only reconcile if the lookup lowercases.
Lexer's own confirmations close the loop: varmint casing (`AMMO_RIFLE`) and Empty
Bottle (`GENERIC_BOTTLE`) render, so that path demonstrably works.

`editor/assets/item-icons/prepare_casing_generic_textures.py` authored the custom
DDS files as `LEX_CASING_225.dds` etc., so the builder filed them under
`joaat("LEX_CASING_225") = 0x9B455FDD`. The game asks for
`joaat("lex_casing_225") = 0x3448E7D9`. That hash is absent from the file.

Verified against the shipped artefact
(`editor/assets/item-icons/generic_textures.ytd`, SHA-256
`58AD5369...C3CF56EC`), which is a single-file A/B with its own control:

| texture in that dictionary | present under the hash the game computes |
| --- | --- |
| `medal_gold` (Rockstar, lowercase) | yes |
| `LEX_CASING_225` (ours, uppercase) | **no** |

The same test over `LEX_INVENTORY_ITEMS.ytd` and `inventory_items_mp.ytd` returns
`no` for all 17 and all 4 custom textures respectively. One defect, reproduced in
all three rebuilds — which is exactly why Lexer reported "no change" each time.

The positive control is the map icons he remembered working: every custom sprite
in `MyOverhaul/stream/lex_blips.ytd` (`lex_blip_bone`, `lex_blip_card`, ...) and
all 99 `lex_fortification_meter_*` sprites were authored lowercase, hash
identically either way, and render.

### Changes

- `editor/assets/item-icons/prepare_casing_generic_textures.py` — custom texture
  names lowercased, with the hash arithmetic recorded in a comment so this is not
  re-derived. The four crafting materials were added to the same dictionary.
- `MyOverhaul/stream/generic_textures.ytd` rebuilt via the existing
  `BuildYtdDirectory` + CitiCon pipeline: 45 Rockstar sprites + 99 fortification
  meters + `lex_casing_225/307/444/shotgun` + `lex_icon_brass/gunpowder/lead/
  steel` = 152 textures, RSC8, 337,426 bytes.
  SHA-256 `31B026E1F93C698D2F9B7ABD4BB3002E25CF7D13588F1AE558D97FC3FDD47D1F`.
  All 152 verified resolvable under the lowercased hash; zero uppercase names.
- `MyOverhaul/catalog_sp.ymt` — `LEX_BRASS`, `LEX_GUNPOWDER`, `LEX_LEAD`,
  `LEX_STEEL` moved from `LEX_INVENTORY_ITEMS` to `GENERIC_TEXTURES`. That
  dictionary is a novel resource name Story never finishes streaming (its own
  probe recorded `exists=1 loaded_before_request=0`), so those four crafting
  icons were blank for a second, independent reason. The catalog now has zero
  references to it. SHA-256
  `75BA71C2A8E9FB8BF430557E4E0D2A830EA80DED3C5AD514482EAB010DF1F83A`.
- The casing catalog `<id>` values stay UPPERCASE deliberately. That matches
  every vanilla record and is the form proven to work; lowercasing them would be
  an unproven second change.
- `GameplayTweaks/modules/items_casings.cpp` needs no edit: it passes
  `"LEX_CASING_225"` / `"GENERIC_TEXTURES"` to natives that lowercase-hash, so it
  now resolves. That file was not touched.
- `tools/reverse-engineering/verify_inventory_icons_issue_11.py` previously
  printed PASS through every blank-icon build because it never opened the
  dictionary. It now decompresses the YTD and asserts each catalog-referenced id
  is present under `joaat(lower(id))`. Against the old shipped YTD it fails;
  against the new one it passes.

### Deployment

`lml/MyOverhaul` is a directory junction to `C:\RDR2Mod\MyOverhaul`, so both the
rebuilt YTD and the catalog edit are already live in the game folder. No OpenIV
step and no file copy are required. Both are startup-loaded, so a **full game
restart** is mandatory.

### Still open, separate from the icon defect

`GameplayTweaks.casings.log` shows `PICKUP_LEX_CASING create failed - falling
back to plain object` on every ejection, so casings spawn as plain objects and
the native-pickup acquisition card never fires. That is a pickup-registration
problem in `items_casings.cpp`, not a texture problem, and it is why "no
acquisition log popups" persisted independently of the artwork.

### Runtime acceptance

1. Full restart. Open the satchel: the pistol/revolver/repeater/rifle casing
    records must show the `.225`/`.307`/`.444` drawings and the shotgun hull its
    own art — no blank squares.
2. Brass, Lead, Steel and Gunpowder must show their drawings in the satchel and
    in crafting ingredient lists.
3. `.225 Round (AP)`, Empty Bottle and varmint casing must still show their
    working vanilla icons (regression check on the 45 preserved sprites).
4. The fortification meter must still render (same dictionary, rebuilt).
