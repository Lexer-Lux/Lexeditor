# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286610161 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/41

Created: 2026-08-29T12:50:45Z; updated: 2026-09-04T12:24:49Z

Exact metadata: [source record](sources/issue-5286610161-bc3578bc8b6f80946a16c77dd000e6705b5f8ccc07f331e6d28ec535513c83d9.json).

Use one shared portrait selector for FF8 GFs and Characters, generated from the player's installed menu assets.

The selector row is also the record identity header. Show the selected name on the unused left side and its darker prefixed numeric ID on the unused right side. Do not repeat name and ID in a separate large detail header.

Acceptance:
- GFs and Characters use the same reusable portrait-selector component.
- Each selector shows the matching in-game portrait with no name text inside the portrait button.
- The selected name appears at the left edge of the selector row and its `#ID` at the right edge.
- Clicking a portrait opens that record's editable detail view.
- Hover text and accessible labels identify the record.
- The selected portrait has a clear state.
- Portraits are generated privately from the installed game and are not bundled.
- Missing or invalid portraits show an explicit fallback instead of wrong art.
- No second name/ID detail header remains.
- Both views are visually checked at 1280x720 and 1600x900.


## issue 5286610161 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/41

Created: 2026-08-29T12:50:45Z; updated: 2026-09-06T13:16:39Z

Exact metadata: [source record](sources/issue-5286610161-1b525bf201d717a93f0b9bdc0277a19a5cc0b5f4ccbef37fee1e41266a67acb5.json).

**Status: Closed after implementation.** Characters and GFs share the installed-game portrait selector. The selected name and darker numeric ID occupy the selector row, without a second identity heading; missing portraits use an explicit fallback.

## comment 5462543123 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/41#issuecomment-5462543123

Created: 2026-08-29T12:57:48Z; updated: 2026-08-29T12:57:48Z

Exact metadata: [source record](sources/comment-5462543123-a066887be230c6ea3e080a63e6bf72e4c7bde61c4f2d7639fb074dd765fef444.json).

GFs and Characters now use one shared portrait selector built from the installed game's `face1.tim` and `face2.tim` sheets. The buttons show only the real in-game portraits; hover text identifies each one, and clicking one opens that record's live editable detail view. I checked all 27 portraits and both selection paths at 1280×720 and 1600×900. Restart LEXEDITOR once before checking it because the portrait URL is part of the FF8 service.

## comment 5464236174 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/41#issuecomment-5464236174

Created: 2026-08-29T18:53:47Z; updated: 2026-08-29T18:53:47Z

Exact metadata: [source record](sources/comment-5464236174-b9a9fe1a44fb122b5609f98a17da92c179c114bbac01130523675cefb1eb7864.json).

The portrait contract had been preserving the bad 58-pixel landscape buttons. Character and GF portrait buttons now use the source art's 2:3 aspect ratio, render at 64×96 on the tested layouts, and let the art fill the 60×92 content area. Characters now shows fixed General and Stat Coefficients headers with no collapsibles. Both tested window sizes loaded every portrait with no overflow. Restart Lexeditor to check the new scale.

## comment 5464934401 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/41#issuecomment-5464934401

Created: 2026-08-29T21:16:59Z; updated: 2026-08-29T21:16:59Z

Exact metadata: [source record](sources/comment-5464934401-4722e5f95b6be75e98c829579cd06a82c34a5f29e7807cc8e5ba4f154055743e.json).

Characters and GFs now use the portrait strip as the identity header: selected name at left and the darker #ID at right. The repeated Character header and GF General ID are gone. Both portrait views passed at 1280 x 720 and 1600 x 900 with all installed portraits loaded and no overflow.
