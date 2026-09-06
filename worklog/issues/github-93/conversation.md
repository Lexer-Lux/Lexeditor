# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5349503543 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/93

Created: 2026-09-04T14:46:05Z; updated: 2026-09-05T06:23:50Z

Exact metadata: [source record](sources/issue-5349503543-afd107258936536a7bd7edfa50bb980febd13514c096d5d80faa1b4e10b4e02d.json).

Give each GF a configured, ordered spellbook. The Magic command must show that GF's complete list in its configured pages and order even when the character owns zero copies. A zero-stock spell stays visible, grey, and unusable. Some spellbook slots are unlocked by GF abilities; those slots stay grey until the ability is learned and still require nonzero spell stock to cast. The editor must expose each GF's spellbook order, page, spell, and optional ability prerequisite as mod data.

## issue 5349503543 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/93

Created: 2026-09-04T14:46:05Z; updated: 2026-09-06T12:46:10Z

Exact metadata: [source record](sources/issue-5349503543-895b3054889296f5269288708d26f72b4f5e20c3076584771bbae8dd7cc5167a.json).

Give each GF an ordered, editable spellbook with pages, visible zero-stock spells and optional learned-ability requirements.

**Not delivered:** the draft used an unsafe memory region, was disabled and was not installed. Safe runtime storage and editor integration remain unfinished. There is no spellbook build for you to test yet.

## comment 5549952649 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/93#issuecomment-5549952649

Created: 2026-09-05T06:23:50Z; updated: 2026-09-05T06:23:50Z

Exact metadata: [source record](sources/comment-5549952649-c19c726ba5ebedd8107745967c78155e58a46d1ea8ec526492118d6860cfe488.json).

GF spellbooks remain deferred. The draft has an ordered-book model and native instruction tests, but integration found that its proposed memory area contains executable resources. It must use loader-owned memory before it can safely run. The draft patch is disabled and its unfinished editor integration is being removed. No spellbook patch was installed. A future implementation still needs live battle checks for page order, locked and empty spells, cancellation, and stock use.
