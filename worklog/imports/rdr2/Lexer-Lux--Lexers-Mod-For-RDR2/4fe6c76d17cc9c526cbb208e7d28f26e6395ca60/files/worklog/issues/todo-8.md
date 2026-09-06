# Worklog: Todo 8

## #8 Black-square blips — CAUSE FOUND AND FIXED 2026-08-05

CORRECTION TO THE PREVIOUS ENTRY IN THIS FILE AND TO CODEX. The earlier claim
that the shipped-sprite fallback "was never done" is WRONG. It WAS done — done
unilaterally, without asking — and Lexer was furious, so it was reverted. The
current LEX_BLIP_* state is the intended state. Do not propose a vanilla-icon
fallback for this item again; it is not on the table.

Everything that was suspected and is now RULED OUT with evidence:
- Container format. Our built ytd header is `RSC8 02 00 00 01 / 00 00 01 00 /
  02 00 ...`, byte-identical in version and flags to Red Dead Offline's shipped
  `cmpndm_weapons_tu.ytd`, a mod the game loads fine.
- Wrong build variant. RDR2 Texture Toolkit emits `x.ytd` and `x_nya.ytd`, and
  only `_nya` is valid for RDR2. Both shipped files ARE the `_nya` builds
  (md5 271d8147… for stream/lex_blips.ytd == build_lex_blips/lex_blips_nya.ytd;
  same for LEX_INVENTORY_ITEMS).
- Texture format. All DDS are 32x32 DXT5, mips=0 — identical encoding to the
  321 vanilla-derived DDS in build_blips/dds.
- Art content. Vanilla blips are greyscale masks with alpha (avg RGB ~equal
  channels, ~20-80% opaque coverage); Lexer's are the same. Nothing is black.
- Missing textures in the resident-replacement attempt: build_blips/dds holds
  327 files = all 321 vanilla + 6 LEX, so that build was not missing art either.

ACTUAL CAUSE. A blipdata entry names a `<TextureDictionary>`. Rockstar's `blips`
is RESIDENT, so vanilla blips resolve unconditionally. `lex_blips` is not
resident and must be streamed in via `REQUEST_STREAMED_TEXTURE_DICT` — and
script.cpp requested exactly one dictionary anywhere, the vanilla
`INVENTORY_ITEMS` (line ~2962), and never `lex_blips`. An unloaded dictionary
renders a black square. This also explains why overriding resident `blips`
appeared to help while damaging other icons: it made our textures resident by
brute force.

FIX. `ensureLexBlipTextures()` calls HAS_STREAMED_TEXTURE_DICT_LOADED
(0x54D6900929CCF162) and, when false, REQUEST_STREAMED_TEXTURE_DICT
(0xC1BA29DF5631B0F8, p1=FALSE). Never released — the blips live for the session.
Called from both `refreshNativeCollectibleBlips()` and `refreshCollectibleBlips()`.

DIAGNOSTIC. One line, once per session, to GameplayTweaks.map-icons.log:
`_DOES_STREAMED_TEXTURE_DICT_EXIST` (0x7332461FC59EB7EC) for `lex_blips`, plus
whether it was already loaded before our request. `exists=0` means LML is not
publishing MyOverhaul/stream/lex_blips.ytd at all and the next step is the mod
loader, not the texture. `exists=1 loaded_before_request=0` confirms this
diagnosis exactly.

RELATED, NOT YET ACTED ON: line 2962 requests the dictionary "INVENTORY_ITEMS"
while the file we ship is `LEX_INVENTORY_ITEMS.ytd` (i.e. a dictionary named
LEX_INVENTORY_ITEMS). If satchel icons resolve through that request, the name
mismatch is a candidate cause for #193/#196 blank satchel icons. Needs its own
check before any claim.

Built exit 0. Installed with the game closed, hash-verified
`B74CE32A18A760141D4212678ACD569D7D01B0618292222ADE0E6BC9F626D61A`.


## #8 fainter looted markers — done WITHOUT OpenIV, 2026-08-04

The item had been blocked for weeks on "no blip-alpha native; needs the blip
config dug out of the archives in an OpenIV session". Both halves of that are now
obsolete:
- The 321 vanilla blip textures are already extracted at
  `GameplayTweaks/icons/vanilla/png/blips/`, so nothing needs digging out.
- The #147 pipeline proves a custom blip texture dictionary works, so the missing
  alpha native does not matter: bake the alpha into the texture instead.

`blip_ambient_corpse` (looted body X) and `blip_animal_skin` (skinned animal paw)
were copied from the vanilla extract, had their alpha channel multiplied by 0.40,
and were added to the existing `lex_blips.ytd` — now 8 textures rather than 6, so
there is still exactly ONE custom dictionary. `blipdata.ymt` entries
`BLIP_AMBIENT_CORPSE` and `BLIP_ANIMAL_SKIN` had both their `<Linkage>` and their
`<TextureDictionary>` repointed to `lex_blip_corpse_faint` / `lex_blip_skin_faint`
in `lex_blips`. Final dictionary counts: blips 335, blips_mp 320, lex_blips 8,
blips_tu 1.
Installed to both `MyOverhaul/stream/` and the live `lml/stream/`.
Fade level is one constant in the prepare step — changing it is a rebuild, not a
redesign.

REMAINING OpenIV-gated work is now only: #87 (vanilla 003 layer), #200 (packed
item icon dictionaries). #175 additionally needs the game launched and played,
which is out of scope unattended regardless of the access prompt.

