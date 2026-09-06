# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5287076771 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/48

Created: 2026-08-29T14:21:59Z; updated: 2026-09-04T12:24:56Z

Exact metadata: [source record](sources/issue-5287076771-a193ccd3e5235ca1f5b15cf89f1979f66338e57acdb73e7a2b528b113c84a906.json).

Displayed numeric values must use separator commas. Example: 1000 is shown as 1,000 and 20000 as 20,000. This is a shared presentation rule across plugins. Editable browser number inputs remain valid raw numeric values while focused because type=number does not accept commas. The shared formatter must also prevent plugin-specific digit-spacing and grouping differences. FF8 item and weapon price displays are the first migration target.

## issue 5287076771 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/48

Created: 2026-08-29T14:21:59Z; updated: 2026-09-06T13:16:50Z

Exact metadata: [source record](sources/issue-5287076771-a27b38047c0e6a108e6b844b2277e1b58abe60bf8874cac3f74ea38f8e336f3b.json).

**Status: Closed after implementation.** Displayed values use grouping commas without making numeric inputs invalid. FF8 price fields retain the game font; calculated Sell Price remains read-only.

## comment 5462952749 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/48#issuecomment-5462952749

Created: 2026-08-29T14:25:50Z; updated: 2026-08-29T14:25:50Z

Exact metadata: [source record](sources/comment-5462952749-146eb2041fd4e1429cce37e75ad85accd9e1ff22469ba273217476fe21e19797.json).

Displayed numbers now use one shared comma-grouping component. FF8 Item Buy/Sell values, calculated Sell Price, Weapon Upgrade Price, shared table cells, and numeric reference values now show forms such as 1,000 and 20,000. Number inputs remain raw while editing because browser number fields reject commas. The shared numeric style also stabilizes digit spacing. Hidden-window checks passed with no overflow.

## comment 5464105949 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/48#issuecomment-5464105949

Created: 2026-08-29T18:25:45Z; updated: 2026-08-29T18:25:45Z

Exact metadata: [source record](sources/comment-5464105949-4c1f9d55f6ed7d60f40b7e70511ca5d79058739e7f9e74d0680406bb5a275c0f.json).

Fixed the remaining 1/0 spacing defect. Commas were correct, but the generated FF8 font's digit metrics still created the false gap. Displayed numbers now use bundled Lexend for stable spacing; surrounding game labels and units keep the FF8 font.

## comment 5464928288 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/48#issuecomment-5464928288

Created: 2026-08-29T21:15:38Z; updated: 2026-08-29T21:15:38Z

Exact metadata: [source record](sources/comment-5464928288-7e47733fe298e47523c933297df3e361622040f6f3882863095257b60d099ac4.json).

FF8 Buy/Sell numbers now use the generated FF8 menu font again instead of Lexend. Comma grouping, disabled calculated Sell fields, and stable kerning remain. The hidden render confirmed the list values, Buy input, Sell output, and G units with no overflow or script errors.
