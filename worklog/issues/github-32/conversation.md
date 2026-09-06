# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286207398 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/32

Created: 2026-08-29T11:13:59Z; updated: 2026-09-04T12:24:42Z

Exact metadata: [source record](sources/issue-5286207398-38c635180024296fc7859883b6a52fb96f4b40d8fe594bf0eeddd0413391491c.json).

Replace the FF8 GFs list-detail screen with one subtab per Guardian Force and a fixed three-panel editor.

Layout:
- GF subtabs select the active GF without leaving the GFs primary tab.
- Left panel: Compatibility.
- Center panel: General.
- Right panel: Abilities.
- Each panel scrolls independently when its content exceeds the available height.
- Use the existing schema-backed controls, help, vanilla values, reference values, undo/redo, dirty state, and kernel save path. Do not duplicate fields or add free-input controls.

Acceptance:
- All 16 GFs are reachable through subtabs.
- Every section-3 field appears exactly once in the correct panel.
- General is the center panel.
- Changing GF preserves unsaved edits and does not reset the page.
- Save/readback and baseline-integrity checks continue to pass.
- Verify the real rendered layout at desktop size.

## issue 5286207398 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/32

Created: 2026-08-29T11:13:59Z; updated: 2026-09-06T12:45:21Z

Exact metadata: [source record](sources/issue-5286207398-24453d374797f5064eaf87721316c97a2609dee5be25bc84c4df14ca7c3c77ad.json).

The GF selector, signed Compatibility values and three-panel layout are implemented.

**Work remains:** the latest report says GF graphs still use the old layout. Bring them onto the current shared curve controls, keeping Compatibility left, General center and Abilities right. Preserve all 16 GFs, unsaved edits and save/readback behavior.

## issue 5286207398 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/32

Created: 2026-08-29T11:13:59Z; updated: 2026-09-06T12:45:21Z

Exact metadata: [source record](sources/issue-5286207398-a7051c49998441086ebacdf8095b2c3b0e00c0654c28000f33d071de7b588b7e.json).

The GF selector, signed Compatibility values and three-panel layout are implemented.

**Work remains:** the latest report says GF graphs still use the old layout. Bring them onto the current shared curve controls, keeping Compatibility left, General center and Abilities right. Preserve all 16 GFs, unsaved edits and save/readback behavior.

## comment 5462088806 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/32#issuecomment-5462088806

Created: 2026-08-29T11:25:32Z; updated: 2026-08-29T11:25:32Z

Exact metadata: [source record](sources/comment-5462088806-0c7d4c555440a94ee120f144df3742646e8146395b8aa8ce45ef583f15ab9710.json).

The GF editor now has one subtab per GF and the requested three-panel layout: Compatibility on the left, General in the center, and Abilities on the right. All 101 editable GF fields still use the existing typed controls and Vanilla/reference provenance. The 21 schema fields marked read-only remain excluded. The rendered layout fits at 1600x900 without truncated GF names or horizontal overflow.

## comment 5462344441 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/32#issuecomment-5462344441

Created: 2026-08-29T12:11:23Z; updated: 2026-08-29T12:11:23Z

Exact metadata: [source record](sources/comment-5462344441-eacf280afc4bdcc43280c7dc07b7e916b23d47c4bbcc4bc15d99891f88bb9510.json).

GF Compatibility now uses signed player-facing modifiers instead of FF8's biased stored bytes. The fields show values such as +5, 0, and -10; Vanilla and reference markers use the same format. Lexeditor converts at the save boundary: +5 writes 105 and -10 writes 90. Hidden Edge entered both values, saved them to a temporary project, read the bytes back, and reloaded the same signed display.

## comment 5487505331 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/32#issuecomment-5487505331

Created: 2026-09-01T01:49:05Z; updated: 2026-09-01T01:49:05Z

Exact metadata: [source record](sources/comment-5487505331-5da08c200b78f568a82806df21e0ae325c515545aeab7051f1c252ebccee9bf7.json).

Repaired GF panel geometry. The portrait-to-panel gap no longer includes the old per-panel top margin, headings remain visible, horizontal overflow is clipped at each panel, and the center/right divider stays stable across its drag range. Compatibility reference text is also large enough to read.

## comment 5539022058 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/32#issuecomment-5539022058

Created: 2026-09-04T10:16:13Z; updated: 2026-09-04T10:16:13Z

Exact metadata: [source record](sources/comment-5539022058-f2ce2e56c025d9b99281942f8bc5ea713c92ddf19617acd8d25eb54eb4cafc03.json).

GF graphs are using an older curve layout: axes are inside the plot, the variable drawer is vertical, and the equation does not follow the curve. Use the same current curve component and outer axis margin as the Character graphs.
