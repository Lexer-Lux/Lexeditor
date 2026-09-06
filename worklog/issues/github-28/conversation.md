# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286109841 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/28

Created: 2026-08-29T10:52:39Z; updated: 2026-09-05T07:26:44Z

Exact metadata: [source record](sources/issue-5286109841-ebcb43e93a1abc553928ff8a46eff8e772cfe7c2ab31207843d35e574b0a301f.json).

Values with real units should show those units everywhere.

- Use a shared unit-bearing field component instead of plugin-specific text.
- Keep the editable input limited to the value. The unit is visible and not editable.
- Use authentic game symbols when available, such as the FF8 G glyph for Gil.
- Cover currency, percentages, time, distance, quantities, and other schema-defined units.
- Do not infer a unit when the source does not establish one.

Acceptance:
- FF8 prices consistently show the game G symbol, not only sell price.
- Existing bounded controls keep their validation.
- Shared styles work across plugin themes.
- A rendered check confirms alignment and spacing.

## issue 5286109841 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/28

Created: 2026-08-29T10:52:39Z; updated: 2026-09-06T13:30:56Z

Exact metadata: [source record](sources/issue-5286109841-429d9c5ab0b101427592485b69bab9773865cfd9e842ed438d4e0ceaadd04157.json).

**Needs testing.** The field repairs are ready for review.

- [ ] Restart Lexeditor. In FF8 Items, check Buy Price, Sell Multiplier and Sell Price: G/× stay inside borders, only numbers are editable, and Sell Price remains read-only.
- [ ] In Blank, edit a number and drag a slider. Limits should replace the type while editing, references should stay aligned, and the released value should persist.
- [ ] Report clipping, incorrect units or jumpy sliders with the field name and screenshot.

## comment 5461948964 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/28#issuecomment-5461948964

Created: 2026-08-29T11:00:19Z; updated: 2026-08-29T11:00:19Z

Exact metadata: [source record](sources/comment-5461948964-bfe5949f8e88b923d666031386b8c46b65fd0839442a4bc4c12571c4275ac45d.json).

Added one shared unit-bearing field component. FF8 now shows its game-font G for item buy and sell prices and weapon upgrade prices, including list columns, while inputs remain numeric. Flying EVA also uses the same non-editable unit treatment. Parser/save and rendered checks passed.

## comment 5464200818 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/28#issuecomment-5464200818

Created: 2026-08-29T18:46:07Z; updated: 2026-08-29T18:46:07Z

Exact metadata: [source record](sources/comment-5464200818-82d42feb7d1a208ed81fbc1e800b59f9316717021055683c5367c0d2a635c1d5.json).

The original shared unit component explicitly kept units outside the field, so its verifier preserved the wrong layout. The shared component now puts prefix and suffix units inside the field border. Multipliers use ×, and derived values use a muted disabled/read-only input. FF8 Items now shows internal G / × / G fields for Buy Price, Sell Multiplier, and Sell Price. Static, save/readback, rendered geometry, and hidden-host checks passed. Restart Lexeditor and check the spacing at your normal display scale.

## comment 5550282384 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/28#issuecomment-5550282384

Created: 2026-09-05T07:26:42Z; updated: 2026-09-05T07:26:42Z

Exact metadata: [source record](sources/comment-5550282384-bdb83c5db755dbe45761ed6508b2d69f225a544e14768c3edc4bdf10712fce2c.json).

Shared field repairs are in place: parameter types are rotated 90 degrees counterclockwise; min/max replaces the type during editing; V/R1/R2 values align; and the details sort marker uses the same centered slot as type/help text. Blank now connects that marker to the selected table sort. Slider handles are translucent, pointer updates are limited to one per display frame, and drag listeners are cleaned up on release or cancellation. Rendered Blank and FF8 checks passed, including live value changes and the final released value. Please check the feel and appearance in the editor.
