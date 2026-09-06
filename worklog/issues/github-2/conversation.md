# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5200987691 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/2

Created: 2026-08-20T07:44:07Z; updated: 2026-09-04T12:24:26Z

Exact metadata: [source record](sources/issue-5200987691-a7e5161fdfd09220cc56105cbf2abb24cb7e77d53f4196924b8fa24f514462ef.json).

## Goal

Add an eye control to the RDR2 Items detail pane. It opens the actual installed item model in a rotatable, zoomable viewer inside the existing Lexeditor window.

## Current working slice

- Weapon YDR geometry and game textures render through the bundled read-only RPF extractor.
- The viewer assembles baseline weapon parts from catalog model families.
- Generated previews use a bounded cache under Lexeditor's local game-data folder.
- The model library is not extracted during setup. The requested asset and its dependencies are generated on demand.

## Reported coverage defect

A carbine renders, but known visible consumables do not:

- Canned Peaches: `CONSUMABLE_PEACHES_CAN` / `S_CANRIGPEACHES01X` is a non-weapon YDR.
- Aged Pirate Rum: `CONSUMABLE_AGED_PIRATE_RUM` / `S_AGEDPIRATERUM01X` is a YFT.
- Jerky: `CONSUMABLE_JERKY` / `S_SALTEDBEEF01X` is a YFT.

The eye currently enables from the catalog model name. The viewer then fails because its archive resolver covers only weapons and its geometry path covers only YDR.

## Acceptance

1. Canned Peaches renders from `levels_3.rpf` -> `levels/rdr3/props/lev_des/s_pickups.rpf` -> `s_canrigpeaches01x.ydr` with its installed textures.
2. Aged Pirate Rum renders from the same archive chain and its real `s_agedpiraterum01x.yft` drawable with its installed textures.
3. Jerky renders from its real `s_saltedbeef01x.yft` drawable.
4. Drag rotates, the wheel zooms, and Reset restores the camera.
5. A second request uses the generated cache.
6. An item with no model has a disabled eye with a useful explanation.
7. An item whose installed asset is not previewable does not show a clickable eye that opens only to report failure.
8. The viewer never substitutes an icon or sample shape.

## Storage policy

Keep extraction lazy. Do not pre-extract the full item model library. Cache one unique asset once, apply the configured cache limit, and keep all generated data outside the game and mod folders.

## issue 5200987691 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/2

Created: 2026-08-20T07:44:07Z; updated: 2026-09-06T13:16:22Z

Exact metadata: [source record](sources/issue-5200987691-06bb5dd92767af94b083b23f7a5dce943ed846555a688aba137f813a6678cfbe.json).

**Status: Closed after the model-preview implementation.** Supported weapons and consumables use their actual installed geometry and textures, with lazy caching, rotation and zoom. The later washed-out-color repair passed rendered checks. This does not claim every game model is supported.

## comment 5353162046 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/2#issuecomment-5353162046

Created: 2026-08-20T08:06:44Z; updated: 2026-08-20T08:06:44Z

Exact metadata: [source record](sources/comment-5353162046-c4abeff9ce2815730a5878d4b9a509a9779d7534fe24ca61bce68f20eb5f5bf4.json).

Implemented the non-weapon preview repair.

- Canned Peaches now renders its installed YDR model and real label textures.
- Aged Pirate Rum and Jerky now render their installed YFT models and real textures.
- The YFT path reads the fragment's embedded drawable and texture dictionary automatically.
- Models outside the supported archive index keep the eye disabled and do not open an error-only viewer.
- Extraction remains lazy: Lexeditor generates only the selected preview and does not copy the full model library.

The hidden WebGL acceptance check passed for all three consumables and the existing Volcanic Pistol case. Please restart Lexeditor and retry those same items.


## comment 5393857681 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/2#issuecomment-5393857681

Created: 2026-08-24T10:19:09Z; updated: 2026-08-24T10:19:09Z

Exact metadata: [source record](sources/comment-5393857681-e47ddb0768a1c55dd17ce82611ef6219e5f35f0c7499523d19ceda19d454e721.json).

Changed preview loading so it no longer opens an empty modal. The eye becomes a throbber while the real asset and geometry are prepared, and the viewer appears only when the model is ready. If you select another item, change tabs, or trigger a rerender first, the finished task stays silent and cached for the next click. Removed the Cached / Extracted now badge. The real hidden render test passed for the pistol, Canned Peaches, Aged Pirate Rum, and Jerky.

## comment 5393901013 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/2#issuecomment-5393901013

Created: 2026-08-24T10:23:29Z; updated: 2026-08-24T10:23:29Z

Exact metadata: [source record](sources/comment-5393901013-9d29092da8a8c11cdf607bcd5d02b424811a4d4f449fbc994453871c3b2d9991.json).

Removed the model viewer's Reset button and bottom action area. Close is now the new shared icon-only close control in the viewer's top-right; the component's size, cross glyph, colors, hover state, title, and accessible label live in the common UI framework for reuse. Double-click still resets the model. The full real-model render and interaction suite passed.

## comment 5394032098 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/2#issuecomment-5394032098

Created: 2026-08-24T10:36:19Z; updated: 2026-08-24T10:36:19Z

Exact metadata: [source record](sources/comment-5394032098-72f01102f7cb5322fd01130b79d579d1bb08380a5d1848c3c9c41aa441271f5e.json).

Fixed the reported preview recurrence.

- `LEX_CASING_VARMINT` now has a disabled eye because its `s_shell_22wrf` asset is outside the supported archive index.
- Cigarettes now remove their stray fragment triangle and render as a normal-sized textured box.
- Potent Bitters now renders its `standard_glass` and solid material meshes instead of opening the material error.
- Texture direction and the starting camera were corrected, so labels are upright and flat items start from above.
- Preview preparation now stays behind the item panel with a spinner. The model window opens only after real geometry is ready, and it cannot appear after you select another item.

Please reopen Lexeditor and retry Canned Peaches, Cigarettes, Potent Bitters, and the Varmint Casing eye.

## comment 5435213266 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/2#issuecomment-5435213266

Created: 2026-08-27T06:27:03Z; updated: 2026-08-27T06:27:03Z

Exact metadata: [source record](sources/comment-5435213266-36c6d7f373475c09c9fb1d4ca927ccf85db2924bacadc4c75bb07e4c7e9453a9.json).

Corrected the washed-out preview rendering. Diffuse textures now enter lighting in the correct color space, the viewer no longer forces a blue-grey tint onto weapon layers, and the old exposure curves that lifted and desaturated the output are gone. The real hidden WebGL suite passed again for the Volcanic Pistol, Canned Peaches, Aged Pirate Rum, Jerky, Cigarettes, and Potent Bitters. Some game textures are deliberately pale, but Lexeditor no longer adds its own bleaching.
