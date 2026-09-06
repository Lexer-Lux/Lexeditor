# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286943792 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/47

Created: 2026-08-29T13:56:18Z; updated: 2026-09-04T12:24:55Z

Exact metadata: [source record](sources/issue-5286943792-8135bf3ff1ba64772e0a4fca829918b911312096cf6e05b77c793bb3d5f6d60d.json).

Repair the FF8 Data Map presentation and inventory.

Requested behavior:
- Filename cells use the active FF8 plugin font instead of the shared monospace filename face.
- Remove the synthetic `Models and textures` row.
- Remove the synthetic `Music and audio` row.
- Keep actual extracted or editor-relevant gameplay files unchanged.

Acceptance:
- The Data Map API does not return either removed synthetic row.
- Hidden Edge shows Filename cells in the FF8 menu font.
- Search/status controls and the remaining Data Map rows still render normally.

## issue 5286943792 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/47

Created: 2026-08-29T13:56:18Z; updated: 2026-09-06T13:16:48Z

Exact metadata: [source record](sources/issue-5286943792-b480ee4ee5c80995f5393034683add24a525351777f0671b7636cde43454cc56.json).

**Status: Closed after the FF8 Data Map cleanup.** Filenames use the game font; synthetic Models/Textures and Music/Audio rows were removed. Notes wrap when necessary, and search/status controls remain usable.

## comment 5462817247 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/47#issuecomment-5462817247

Created: 2026-08-29T13:57:58Z; updated: 2026-08-29T13:57:58Z

Exact metadata: [source record](sources/comment-5462817247-b6d220a7c9c419cd522c795a65e0ccd86df9fa6f8947359475ce3ca2d9a6976a.json).

Fixed the FF8 Data Map.

- Filename cells now use the FF8 menu font.
- Removed the synthetic `Models and textures` row.
- Removed the synthetic `Music and audio` row.
- Kept the 11 actual gameplay/editor entries and the existing search, status, sorting, and paging behavior.

A hidden render confirmed the computed filename face is FF8 Menu and neither removed row reaches the UI. Restart Lexeditor once if FF8 is already open.

## comment 5472579038 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/47#issuecomment-5472579038

Created: 2026-08-31T01:27:18Z; updated: 2026-08-31T01:27:18Z

Exact metadata: [source record](sources/comment-5472579038-ea9836c3e0f06ad61999525aeb86173abc4a0ac4c5f43ad4ea731ee833e46122.json).

Data Map Notes now wrap to several lines instead of being forced into one unreadable row. The rendered FF8 table keeps the game font, all 13 real data rows, and the bottom search/filter bar without a horizontal overflow.
