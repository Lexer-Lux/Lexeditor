# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286642098 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/42

Created: 2026-08-29T12:58:13Z; updated: 2026-09-04T12:24:50Z

Exact metadata: [source record](sources/issue-5286642098-6da15088015698555dafc0b8654622dade76b80462e65d1938393d70a54e6370.json).

The active-tab arrow is visibly lower than the tab label in the FF8 main navigation.

Acceptance:
- The arrow and label share one vertical center.
- The repair applies to every FF8 main tab.
- Tab width and label centering remain stable.
- Verify the rendered alignment at 1280x720 and 1600x900.

## issue 5286642098 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/42

Created: 2026-08-29T12:58:13Z; updated: 2026-09-06T13:16:40Z

Exact metadata: [source record](sources/issue-5286642098-cf1198379a705a188a99dacc41e29f97280fd09cf64adbc116ebae444160db0f.json).

**Status: Closed after the alignment repair.** Active markers and labels share a vertical center. Shortcut prompts appear only on hover/focus with reserved space, so they do not push or overlap the label.

## comment 5462567901 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/42#issuecomment-5462567901

Created: 2026-08-29T13:03:16Z; updated: 2026-08-29T13:03:16Z

Exact metadata: [source record](sources/comment-5462567901-8295fd661b31003edd6925f074a5b6d0543597d9d63103abb26b88f44a8accfa.json).

The active-tab marker no longer uses a font glyph or baseline offset. It is now a geometric CSS triangle inside the same centered flex row as the label, so both share one vertical center. I rendered and checked Shops at 1280×720 and 1600×900 with no tab-width or overflow regression.

## comment 5464236245 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/42#issuecomment-5464236245

Created: 2026-08-29T18:53:48Z; updated: 2026-08-29T18:53:48Z

Exact metadata: [source record](sources/comment-5464236245-6f89923cf73e5fe031d5fb2dcc3a1ff4f1de943ea469982cc2ae87f79519d114.json).

Yes, this was a font-metric problem. The triangle was geometrically centered, but FF8's uppercase ink center sat 152 font units above the declared line-box center. It is the same class of problem as RDR Lino, but from independent metrics in the FF8-generated face. I corrected FF8 Menu once at the font-face level, so tabs, tables, headers, and controls all move together. Hidden renders passed at 1280×720 and 1600×900.

## comment 5538726689 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/42#issuecomment-5538726689

Created: 2026-09-04T09:49:21Z; updated: 2026-09-04T09:49:21Z

Exact metadata: [source record](sources/comment-5538726689-2f9ae885811c840b2b0ec8d8456041f9e5ad8aa3c4f9dde48c62d4b13af7fd21.json).

Tab shortcut prompts must stay hidden until that tab is hovered. The label needs equal left and right inset, and the prompt must fit inside that reserved inset without covering the label.

## comment 5538850844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/42#issuecomment-5538850844

Created: 2026-09-04T10:01:09Z; updated: 2026-09-04T10:01:09Z

Exact metadata: [source record](sources/comment-5538850844-5c8d93fbc2dd04102c42059b1b3e8f39f3771793c39e1f1b20fa0dda49172947.json).

Fixed the shortcut prompts in the shared tab control. They are now hidden until the tab is hovered or keyboard-focused. Main tabs and subtabs reserve equal space on both sides of the label, and long text clips inside that space instead of painting under the prompt. A rendered FF8 pointer test confirms the prompt stays inside the tab with zero overlap.
