# Enemy editor controls

The Enemies page keeps Scan text in its Battle Text leading panel; the right
panel contains numeric properties, two rows of booleans, tier tables, cards,
and defenses. Layout is composed in `enemies_ui.js` with shared provenance,
Thing Selectors and Searcher, and styled in `enemies_ui.css`.

## Saving table values

`enemy_tables.read_tables` supplies the canonical `row.tables` entries.
`saveAll` serializes those entries, not presentation copies. A UI row that adds
tier metadata must retain the underlying entry by reference. Otherwise edits
can appear on screen but never reach `apply_edits`.

Draw, Mug and Drops each contain three tiers of four ordered ID/quantity pairs.
The compact display hides only Draw's slot headings; it does not sort, merge,
remove or truncate entries or their stored second bytes. Mug/Drop slot order
and all three card IDs are retained.

Element defense displays `900 - stored * 10`; zero is immunity, negative
values represent absorption, and 100 is neutral incoming damage. The status
shortcut stores 255 (displayed as 155, since display is `stored - 100`). The
immunity button remembers the previous value while the same record is loaded;
existing immune records fall back to neutral when first toggled off.

## Local card pictures

`card_art.py` reads the local `menu.fs/fi/fl` archive. No game images are bundled.
`cardanm.sp2` provides rectangles; `mc00.tex` through `mc09.tex` contain 11 cards
per page. Card ID / 11 selects a texture and ID % 11 selects a rectangle.
The SP2 index begins with a uint32 count and four-byte pointer records; each
uint16 pointer locates an entry with x/y at +4/+5 and width/height at +8/+10.
The TEX v2 header is 240 bytes, followed by BGRA palette entries and indexed
pixels. Source: OpenVIII-monogame `Core/Menu/Images/Cards.cs`, `SP2.cs`,
`Core/Image/Entry.cs::LoadfromStreamSP2`, and `Core/Image/TEX.cs`.
The image endpoint checks card IDs 0–109. The 255 sentinel has no picture.
Missing pictures have a text fallback and do not prevent card selection.

## Regression entry points

`tools/verify_ff8_enemies_layout.py` runs the complete production page with
synthetic installation data and applies its saved payload with the production
binary writer. `tools/verify_ff8_card_art.py` checks synthetic SP2/TEX archives
and actual local HTTP routes. Neither substitutes for installed-game visual
acceptance. The previous search-input regression is retained separately.
