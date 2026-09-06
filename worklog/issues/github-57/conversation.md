# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5288587648 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/57

Created: 2026-08-29T20:02:47Z; updated: 2026-09-04T12:24:58Z

Exact metadata: [source record](sources/issue-5288587648-4da48fa409648a045353c53ebf2188c32ec5d276157149e44d8075af0b0a15d3.json).

FF8 item icons use their source bitmap's intrinsic size even when the surrounding item name is much larger. The fixed-pixel slot and `max-width` rules do not scale the bitmap up.

Make the shared FF8 item-icon component size relative to the surrounding text. The image must fill that relative slot with contained, pixelated scaling. This must work in ordinary table rows, selectors, ingredients, shop stock, and large detail headings without per-view pixel overrides.

Acceptance:
- Icon geometry derives from the current text size rather than a fixed pixel value.
- A detail-heading icon grows with its title text.
- A table-row icon remains proportional to table text.
- The icon remains centered, preserves its aspect ratio, and uses pixelated rendering.
- One component and one CSS rule serve every FF8 item mention.

## issue 5288587648 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/57

Created: 2026-08-29T20:02:47Z; updated: 2026-09-06T13:16:51Z

Exact metadata: [source record](sources/issue-5288587648-b7127ec4436256a706c791ba824dbbbf9376ec55774664610cd9de1a4f033378.json).

**Status: Closed after implementation.** Item icons grow with headings and remain proportional in tables, selectors, shops and ingredient lists. They preserve aspect ratio and crisp bitmap scaling instead of staying at their source pixel size.

## comment 5464606893 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/57#issuecomment-5464606893

Created: 2026-08-29T20:05:20Z; updated: 2026-08-29T20:05:20Z

Exact metadata: [source record](sources/comment-5464606893-0ba1de8bddb3fef11aebf07eef7dcfbe15c330162a29148aa1825e2d8b624414.json).

The bitmap was staying at its intrinsic 16-pixel size because the CSS only set a maximum size. Item icons now use one text-relative `em` size and fill that slot while preserving their aspect ratio.

The rendered Items check measured about 24 px beside normal 17 px text and 43 px beside the 31 px detail title. The same component also serves shops, selectors, and weapon ingredients.
