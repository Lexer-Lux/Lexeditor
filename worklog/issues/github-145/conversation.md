# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356294803 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/145

Created: 2026-08-06T02:27:53Z; updated: 2026-09-05T06:57:21Z

Exact metadata: [source record](sources/issue-5356294803-eb2f4f42503b8989c3644c74c3f2aa5669429fb6bbba627a1fdcf61fed084251.json).

200! REMAINING ITEM ICONS — items showing '?' in LEXEDITOR.
     THE REAL NUMBER IS 633, and it is TWO groups, not fifteen.
     I had this wrong twice. First I said "~15%". Then I counted every icon the
     editor has no LOCAL file for and said 984 — but that was measuring the
     wrong thing, because the editor already falls back to femga's public atlas
     at runtime for anything it hasn't got locally, and that fallback URL is
     correct. 351 of those 984 already render fine; they were never broken.
     What is genuinely absent from femga, and therefore genuinely needs pulling
     out of the game:
       ITEM_TEXTURES   347
       UI_ITEMVIEWER   283
       plus 3 stragglers (INVENTORY_ITEMS_TU 1, WEAPON_TEXTURES_MP001 2)
     Everything else — satchel textures, gunsmith swatches, shaving menu, ammo
     types, multiwheel weapons, item types — femga covers and the editor is
     already pulling. Nothing to do for those.
     So this is ONE OpenIV session for TWO dictionaries. Not fifteen, not 984
     files. Export ITEM_TEXTURES and UI_ITEMVIEWER as PNGs into
     editor/assets/, and Lexer-Lux/Lexeditor#108 already proved nothing further is needed after that.

## issue 5356294803 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/145

Created: 2026-08-06T02:27:53Z; updated: 2026-09-06T12:47:23Z

Exact metadata: [source record](sources/issue-5356294803-c533c5201483f9ff8f094e5be0c9f3aeca322a72a08351ceef290e77f2dd9281.json).

**Status: Partly repaired.** The manual export is already done and supplied 544 local icons. Remaining gaps include 84 unresolved catalog references and two textures the converter cannot decode.

Resolve those references and decoding failures before requesting more exports. Do not ask you to repeat the completed OpenIV session.

## comment 5550121955 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/145#issuecomment-5550121955

Created: 2026-08-06T07:33:47Z; updated: 2026-08-06T07:33:47Z

Exact metadata: [source record](sources/comment-5550121955-cbbf0d0d84773786c0873c5fd959982f1e0f92b8f98228eb2f77c4db36f10f72.json).

The remaining work requires an OpenIV extraction session for game texture dictionaries, which is computer-control/manual asset work rather than an autonomous actionable. Moved to `needs a human`.

## comment 5550121974 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/145#issuecomment-5550121974

Created: 2026-08-13T00:49:09Z; updated: 2026-08-13T00:49:09Z

Exact metadata: [source record](sources/comment-5550121974-4bde96c6025331f7647f32aecef9cec2bd12302396acc271caea1d4b737891c9.json).

I used OpenIV with RDR2 closed and exported the base and update ITEM_TEXTURES and UI_ITEMVIEWER archives. LEXEDITOR now uses 544 new local PNGs: 309 ITEM_TEXTURES records and 235 UI_ITEMVIEWER records. This is a partial repair, not a complete one: 84 unique catalog references are not present under their catalog IDs in those archives, and two resolved DDS files use a pixel format the current converter cannot decode. Those records still show the missing marker; I left this as needs a human rather than claiming the whole gap is fixed.
