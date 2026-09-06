# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5202412299 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/7

Created: 2026-08-20T10:31:11Z; updated: 2026-09-04T12:24:31Z

Exact metadata: [source record](sources/issue-5202412299-3e14805f4b8b50bcfebf7465ba7ae86137825450f0521f79220ddd017868718e.json).

The unified RDR2 editor changed the old standalone save icon by forcing it through the shared monochrome symbol font. Restore the colored floppy-disk appearance.\n\nUse the RDR2 font hierarchy consistently: Chinese Rocks / Redemption for large display text, titles, section headings, record names, and every main tab; RDR Lino for smaller interface copy and item descriptions. Keep technical IDs in a clear monospace font.

## issue 5202412299 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/7

Created: 2026-08-20T10:31:11Z; updated: 2026-09-06T12:44:55Z

Exact metadata: [source record](sources/issue-5202412299-3ab249f011d3b1deb0fef3afd245716112bd98454516515b1157a9ab33f12a0d.json).

The colored floppy-disk icon and RDR2 font hierarchy are restored. Text metrics were also adjusted; appearance needs your check.

- [ ] Restart Lexeditor and open RDR2. Check Save, main tabs, item names and descriptions: the floppy should be colored, headings use the display font, and smaller text remain readable.
- [ ] Resize the window and inspect the bottom list row for clipping. Send a screenshot of any wrong font or alignment.

## issue 5202412299 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/7

Created: 2026-08-20T10:31:11Z; updated: 2026-09-06T12:44:55Z

Exact metadata: [source record](sources/issue-5202412299-81936ff43c9cce94234b85d4abe3e9ed24c45a57ddf1da4a400a61889d8f7c19.json).

The colored floppy-disk icon and RDR2 font hierarchy are restored. Text metrics were also adjusted; appearance needs your check.

- [ ] Restart Lexeditor and open RDR2. Check Save, main tabs, item names and descriptions: the floppy should be colored, headings use the display font, and smaller text remain readable.
- [ ] Resize the window and inspect the bottom list row for clipping. Send a screenshot of any wrong font or alignment.

## comment 5354718857 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/7#issuecomment-5354718857

Created: 2026-08-20T10:34:23Z; updated: 2026-08-20T10:34:23Z

Exact metadata: [source record](sources/comment-5354718857-37c792dfa20b7d6dc7fc6f9f22ef6ccf0b6f3a6a57945ce27db930c36ca5090a.json).

Fixed the theme regression. Save now uses the Windows color-emoji font instead of the shared monochrome symbol font, including while the button is disabled. Every RDR2 main tab and visible item name now uses the Chinese Rocks/Redemption display face; descriptions remain RDR Lino and internal IDs remain monospace. The full hidden RDR2 and Warband render suite passed.

## comment 5355732769 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/7#issuecomment-5355732769

Created: 2026-08-20T12:14:52Z; updated: 2026-08-20T12:14:52Z

Exact metadata: [source record](sources/comment-5355732769-4c1f7046f226233efc243a8c7bdbdf04f56e67249100b0e32eee9f363520358e.json).

Corrected RDR Lino at the font-face level. Its visible glyphs are now optically 5% smaller, the baseline sits lower through corrected ascent/descent metrics, and ordinary text controls have a roomier line height. The full hidden RDR2 and Warband render suite passed; fitted rows and pagination did not regress.
