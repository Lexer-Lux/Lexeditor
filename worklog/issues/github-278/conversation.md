# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356327810 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/278

Created: 2026-08-12T12:33:12Z; updated: 2026-09-05T07:04:25Z

Exact metadata: [source record](sources/issue-5356327810-0c8b48335c4ee29a2c72084a3df8537b15358c34a82bf935c9b88ce9b92fafb2.json).

Keep the main LEXEDITOR header visible at the top of the viewport while the page scrolls. The header includes the LEXEDITOR title, primary navigation, dataset selector, and Save button. Page content must scroll underneath it at wide and narrow widths without clipping menus or breaking the fixed Loot Tables layout.

Acceptance:
- Scroll a long page: the complete header remains at the top.
- The header does not cover the first page content or table headers.
- Dataset controls and Save remain usable.
- Wide and narrow layouts have no horizontal overflow caused by the sticky header.

## issue 5356327810 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/278

Created: 2026-08-12T12:33:12Z; updated: 2026-09-06T13:18:36Z

Exact metadata: [source record](sources/issue-5356327810-98d7d39bf3e152dd483aa732a17ae77a2546cef2e7f8d6868cf584ba16fc21f4.json).

**Status: Closed for the shared sticky-header behavior.** Navigation and Save stay reachable while long content scrolls beneath them. The later transition-wrapper regression and repair are recorded in #59.
