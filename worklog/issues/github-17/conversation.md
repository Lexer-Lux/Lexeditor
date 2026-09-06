# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5264210532 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/17

Created: 2026-08-27T05:27:31Z; updated: 2026-09-04T12:24:36Z

Exact metadata: [source record](sources/issue-5264210532-6736ab46f7bf8542ba91bb5f2c8e6dabc838e00f4ed9986dea2457027299bb9d.json).

## Problem

RDR Online catalog items still show no in-game names in the RDR2 Items view. LEXEDITOR loads its small Story Mode text bundle and mod `strings.gxt2` overrides, but it does not load the installed game's Online text database or follow the catalog's alternate-name keys.

## Required behavior

- Extract only the installed English Online localization database into LEXEDITOR's private cache. Do not bundle Rockstar text or dump all game data.
- Convert it with the bundled read-only headless extractor.
- Resolve a catalog item's primary name and description first, then its `LABEL_TYPE_ALT_NAME` or `LABEL_TYPE_ALT_DESC` reference when the primary key has no text.
- Keep `strings.gxt2` overrides authoritative and editable under the catalog's primary key.
- Refresh the cache when the source game archive changes.
- A failed extraction must be logged and must not report the localization layer as ready.

## Acceptance

With an installed English RDR2 copy, Online catalog records such as Irish Whiskey, Old Tom Gin, and Canned Peaches show their real names in Items and every other view that uses catalog names. Story items and modded localization overrides remain unchanged.

Related to #16, but scoped to the missing Online localization layer and catalog fallback behavior.

## issue 5264210532 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/17

Created: 2026-08-27T05:27:31Z; updated: 2026-09-06T13:16:28Z

Exact metadata: [source record](sources/issue-5264210532-c333a3aa32a7ab4077731a73bcdf903bfa9fefc76f2c103b900d7c90beb34f21.json).

**Status: Closed after the localization repair.** Online names, descriptions and alternate keys use the installed game’s English text; mod overrides remain authoritative. Genuine unnamed records stay unnamed rather than receiving invented labels.

## comment 5434866258 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/17#issuecomment-5434866258

Created: 2026-08-27T05:40:20Z; updated: 2026-08-27T05:40:20Z

Exact metadata: [source record](sources/comment-5434866258-0347a2a4bb54d3864f8739462de1717d4b92f8983c23585d3ff5e9eadc14aa5c.json).

Fixed the missing Online localization layer. LEXEDITOR now extracts the installed English text database into its private cache, resolves direct numeric labels, symbolic labels, and alternate name/description references, and keeps `strings.gxt2` edits authoritative.

I verified the live Items view with `Irish Whiskey Bottle`; the same resolver now returns `Old Tom Gin Bottle`, `Webster Gun Belt`, `Wallingford Hat`, and `Stringham Shirt`. Restart LEXEDITOR so the updated service loads, open RDR2, and check the Online items that were blank before. Internal records that have no label in Rockstar's installed global text remain unnamed instead of receiving invented names.
