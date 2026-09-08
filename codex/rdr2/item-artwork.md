# RDR2 item artwork

## Catalog UI data

RDR2 catalog UI entries are not just image filenames. Decompiled Story code calls
`ITEMDATABASE::_ITEM_DATABASE_FILLOUT_UI_DATA` and iterates up to five UI triples.
The shared lookup helper hashes the first string as the **texture hash/name**, the
second string as the **texture dictionary**, and compares the third field to the
requested **texture type**. Debug-symbol strings in the 1355 multiplayer script
dump explicitly name those parameters `iTextureHash`, `iTextureDictionary`, and
`eTextureType`.

For ordinary inventory artwork the scripts request texture type `INVENTORY` and
dictionary `UI_ITEMVIEWER`. `doc_book` additionally tests the returned texture
hash with `_DOES_STREAMED_TXD_EXIST`, requests it as a streamed TXD when present,
and later applies that TXD to the held document prop with `_SET_APPLY_OBJECT_TXD`.
A catalog texture handle therefore does not guarantee that a same-named static
PNG exists inside one atlas.

Sources used to establish this contract:

- `JayKoZa/RDR2-Decompiled-Scripts`, `script_mp_rel/doc_book.c`, `func_134`
- `Faroeste-Roleplay/rdr3_decompiled_script_mp_rel_tty.1355`, debug strings in the
  shared `FIND_INVENTORY_ITEM_TEXTURE_UI_DATA` helper

## Static UI_ITEMVIEWER layers

OpenIV's RDR2 archive-name database exposes three static UI_ITEMVIEWER layers:

1. `textures_1.rpf` -> `textures/ui/ui_itemviewer.ytd`
2. `update_4.rpf` -> `x64/patch/textures/ui/ui_itemviewer.ytd`
3. `x64/dlcpacks/dlc_content_extra/dlc.rpf` ->
   `x64/textures/ui/ui_itemviewer.ytd`

The historical Lexeditor audit contains 283 raw UI_ITEMVIEWER reference values.
Current accounting is:

- 235 raw values have bundled PNGs under
  `games/rdr2/assets/dictionary_icons/ui_itemviewer`.
- 7 C5/C6 treasure-map values live in the DLC layer and are decoded from the
  installed game on demand by `games/rdr2/inventory_icons.py`.
- 41 raw values (42 unique attempted IDs because two book values contain ordered
  alternatives) have no static atlas entry in any of the three layers.
- Consequently the unresolved **static atlas** count is zero.

The seven installed-game values are `TREASURE_MAP_C5_M1` through `C5_M3` and
`TREASURE_MAP_C6_M1` through `C6_M4`. PR #418 added the read-only installed-game
fallback. It extracts the DLC YTD with the bundled RPF8 reader, normalizes the
reader's decoded RSC8 representation to raw-deflate RSC8, decodes with pinned
`texfury`, and caches only generated PNGs under Lexeditor's private data root.

## Non-static document handles

The 41 non-static raw values are seven book reference values,
`UI_LETTER_MAYOR_PERM`, `UI_MAP_SERIAL_KILLER`, `UI_NOTE_DINO_01` through
`UI_NOTE_DINO_30`, `UI_PHOTO_NORWEGIAN`, and `UI_PHOTO_SC_DAGUERROTYPE`.
They are deliberately classified in `inventory_icons.py`; do not infer aliases
from similar filenames.

Evidence that these are not failed extractions:

- None appears in the named entries of any static UI_ITEMVIEWER layer.
- Their JOAATs are absent from the base atlas unresolved `.hashes` list. A known
  normal entry such as `UI_LETTER_ABIGAIL` does appear there, validating that
  comparison.
- `collectibles_ymt.xml` pairs all 30 dinosaur-bone records with the deliberate
  `UI_NOTE_DINO_01` through `UI_NOTE_DINO_30` handles even though those handles
  have no static atlas texture.
- `post_office_ymt.xml` pairs the corresponding dinosaur mailer transactions with
  their document item IDs.

For these records, the editor's explicit unavailable-artwork state is correct
unless a future source identifies an exact renderable asset. Do not create
similarity-based mappings such as `UI_PHOTO_NORWEGIAN -> UI_NOTE_NORWEGIAN` or
`UI_MAP_SERIAL_KILLER -> UI_MAP_DISC_COMBINED` without source evidence proving
identity.

## Coverage invariants

`tests/test_rdr2_inventory_icons.py` enforces the historical accounting:

- `ITEM_TEXTURES`: 347 bundled static PNGs.
- `UI_ITEMVIEWER`: 235 bundled raw values + 7 installed-game raw values + 41
  non-static raw values = 283 historical raw values.
- Unknown values remain `missing`; the classifier is not a blanket exemption.

`games/rdr2/assets/MISSING_ICONS.txt` is now a status report, not an extraction
to-do list.
