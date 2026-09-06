# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5264309604 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/20

Created: 2026-08-27T05:45:26Z; updated: 2026-09-05T06:28:15Z

Exact metadata: [source record](sources/issue-5264309604-d1e266e5da87672d8a99b0c432e84a5b6083029f8d0bec1c971cba0f3fc347f5.json).

## Goal

Show the real Warband inventory representation for each item. Warband item icons are renders of the first mesh in module_items.py, backed by BRF meshes/materials and DDS textures. Reuse the shared Lexeditor viewer controls, but add a Warband BRF asset path rather than treating BRF as RDR2 data.

Use the installed Warband font atlas (Data/font_data.xml plus Textures/font.dds) for prominent plugin text where it can render accurately. Do not replace it with a guessed TTF.

## Acceptance

- Items expose their mesh identity instead of only name/value metadata.
- A preview control is enabled only when its BRF mesh and texture dependencies resolve.
- The preview uses installed game or active-module assets and does not copy the full asset library.
- The shared viewer interaction remains rotate/zoom/close.
- Prominent Warband labels use the installed bitmap font data where supported; editable body controls remain legible native HTML controls.

## issue 5264309604 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/20

Created: 2026-08-27T05:45:26Z; updated: 2026-09-06T13:30:48Z

Exact metadata: [source record](sources/issue-5264309604-2a6b0f62040f0423e49442c05d45b809f72c4580d7f4bbc3159e1cd399e3046e.json).

**Actionable — delivery remains.** Preview cleanup, cached heading icons and font checks are in draft PR #361, not the normal installed editor. Real BRF/DDS appearance is unverified.

The full model must fit its heading icon; the larger preview must rotate, zoom and reopen without stale assets. Missing textures need an explicit error, not a gray substitute. Game-font text and manuals must remain readable. A ready-to-run test copy still needs preparing.

## issue 5264309604 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/20

Created: 2026-08-27T05:45:26Z; updated: 2026-09-06T13:30:48Z

Exact metadata: [source record](sources/issue-5264309604-d09aa7cf9344544915f7bf4647e3d553dd78c48d14fe2566900f2ba0bfb4c590.json).

**Actionable — delivery remains.** Preview cleanup, cached heading icons and font checks are in draft PR #361, not the normal installed editor. Real BRF/DDS appearance is unverified.

The full model must fit its heading icon; the larger preview must rotate, zoom and reopen without stale assets. Missing textures need an explicit error, not a gray substitute. Game-font text and manuals must remain readable. A ready-to-run test copy still needs preparing.

## comment 5435213790 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/20#issuecomment-5435213790

Created: 2026-08-27T06:27:08Z; updated: 2026-08-27T06:27:08Z

Exact metadata: [source record](sources/comment-5435213790-6a865dc4c20b7463aed58c08651d75242c605887ec146b97ea8a62c97f9c66c5.json).

Added native Warband item previews and typography. Items now reads the first inventory mesh from module_items.py, resolves the installed BRF material and DDS texture in module.ini order, and renders the selected model in the right detail panel. The bundled headless BRF tool includes its license and exact source record. Prominent labels use the installed font.dds atlas and font_data.xml metrics. The live plug-in test rendered tutorial_axe as the real iron_ax mesh and preserved the live settings file. BRF and DDS are marked partial in the Data Map because Lexeditor reads but does not write them.

## comment 5463009721 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/20#issuecomment-5463009721

Created: 2026-08-29T14:37:39Z; updated: 2026-08-29T14:37:39Z

Exact metadata: [source record](sources/comment-5463009721-cfca5613ea623d3fcae36668bf335b75c1246e472db1171d26d7bb14b72e8c40.json).

The supplied screenshot exposed a real atlas-conversion bug: Lexeditor ignored the installed DDS alpha and made transparent dark pixels visible around the glyphs. Warband inventory icons are renders of each item's first 3D mesh, not separate flat images. I am preserving the real atlas alpha and placing that resolved mesh in the detail heading's top-left icon space.

## comment 5463026596 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/20#issuecomment-5463026596

Created: 2026-08-29T14:41:19Z; updated: 2026-08-29T14:41:19Z

Exact metadata: [source record](sources/comment-5463026596-6a881f4065703e292b3e4b1fd17f4f066f232f8673f214ec65c155fb365cc903.json).

Fixed the damaged tab text by preserving the installed font DDS alpha instead of deriving opacity from RGB. Warband's inventory image is the item's first 3D mesh, so the selected item now renders that real mesh in the shared Detail heading's top-left icon space and keeps the full interactive preview below. Please restart Lexeditor and check the tab labels plus one item.

## comment 5549974107 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/20#issuecomment-5549974107

Created: 2026-09-05T06:28:15Z; updated: 2026-09-05T06:28:15Z

Exact metadata: [source record](sources/comment-5549974107-5c349f47005127ceb7522f28a0dd9f4a152de202a331c45e9ddb01a8402f6def.json).

The item header used a fixed 96-pixel icon inside a shorter shared heading, which cut off its bottom. The icon now fits inside the actual heading with space below it. Warband's bitmap-font conversion now preserves the shared tab label and shortcut badge, so the numbers stay centered. Mod Manuals moved from the main tab row into Information.

The ankle-boots rendered check passed: the full icon fits, all four shortcut badges are centered, and Information opens the manuals. The item detail still has no property editor: the current API reads a small item summary and provides a mesh preview, but it has no item-save route. This is missing implementation, not fields hidden behind the preview. Cached still-image icons remain deferred under #78.

