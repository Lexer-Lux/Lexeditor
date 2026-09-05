# Crafting item icon concepts

RDR2-style black-and-white engraved inventory art for these planned/custom
crafting materials:

- `empty-bottle.png`
- `steel.png`
- `lead.png`
- `brass.png`
- `gunpowder.png`

Each icon has a transparent monochrome master plus `-256.png` and `-64.png`
previews. `crafting-material-icons-preview.png` compares the five at working
and inventory sizes. The `*-source.png` files retain the original colored
green-screen generations for future regeneration, but the usable inventory
derivatives are grayscale only.

`build_inventory_ytd.ps1` packs the usable icons into
`LEX_INVENTORY_ITEMS.ytd` and installs the same dictionary to
`MyOverhaul/stream/LEX_INVENTORY_ITEMS.ytd`. Catalog records should point at
`dict=LEX_INVENTORY_ITEMS` with these texture IDs:

- `LEX_ICON_EMPTY_BOTTLE`
- `LEX_ICON_STEEL`
- `LEX_ICON_LEAD`
- `LEX_ICON_BRASS`
- `LEX_ICON_GUNPOWDER`
- `LEX_AMMO_225`
- `LEX_AMMO_307`
- `LEX_AMMO_444`
- `LEX_CASING_225`
- `LEX_CASING_307`
- `LEX_CASING_444`
- `LEX_CASING_REVOLVER`
- `LEX_CASING_PISTOL`
- `LEX_CASING_REPEATER`
- `LEX_CASING_RIFLE`
- `LEX_CASING_VARMINT`
- `LEX_CASING_SHOTGUN`

Generation used the built-in image tool with
`casing-icons-concept-v1.png` as the style reference. The prompt requested a
late-1890s engraved catalog illustration, strong black outlines and
crosshatching, and a clear silhouette at 48x48 pixels on a flat chroma-key
background. Each subject prompt then specified the bottle, steel ingots, lead
pigs, brass ingots, or powder horn. The final editor-facing files are converted
to black-and-white so they match RDR2's radial/inventory language.

`three-caliber-source.png` contains the built-in image-generation source sheet
for the fictional .225, .307, and .444 loaded cartridges and their spent
casings. The six `lex_ammo_*` and `lex_casing_*` files are its transparent,
square inventory derivatives.
