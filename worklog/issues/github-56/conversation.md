# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5288477560 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/56

Created: 2026-08-29T19:38:32Z; updated: 2026-09-05T07:25:03Z

Exact metadata: [source record](sources/issue-5288477560-d65d137fe81f7252b8e08375dec390fd6e59247be749503bf447eaf44e8b46f6.json).

Create one shared help/explainer control for every plugin.\n\nAcceptance:\n- A help marker is a question mark inside a filled circle; never a bare question mark.\n- The shared framework owns its DOM, size, alignment, accessible label, hover/focus state, and theme colors.\n- Plugins call the shared helper and do not create or style field-help markers independently.\n- Informational markers expose useful tooltip text only.\n- Interactive contextual-help toggles can use the same visual primitive with button semantics.\n- Rendered checks cover FF8 and RDR2 field labels.

## issue 5288477560 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/56

Created: 2026-08-29T19:38:32Z; updated: 2026-09-06T13:06:54Z

Exact metadata: [source record](sources/issue-5288477560-1af7c4102536f574eacc38268fbbd25b96c41a109f0f5a3153ae1e192a36281a.json).

**Status: Latest Blank regression is repaired; needs your visual check.** Help uses a filled-circle question mark, centered in the field’s metadata slot, without an oversized cursor covering it.

- [ ] Restart Lexeditor. In Blank, hover a field’s metadata area: the help marker should replace the type text and reveal useful help.
- [ ] Check a narrow window, then FF8 and RDR2 fields. Confirm markers remain centered and readable and keyboard focus exposes help. Report the field and screenshot of any failure.

## comment 5464560681 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/56#issuecomment-5464560681

Created: 2026-08-29T19:56:29Z; updated: 2026-08-29T19:56:29Z

Exact metadata: [source record](sources/comment-5464560681-e196b2269b799690534152cedc511861f3e2f8ba52efa4f396a5bfe70607669d.json).

Implemented one shared help marker for FF8 and RDR2. Field explainers and the contextual help toggle now use a filled circular `?`, with the game's theme color, useful hover text, and keyboard focus. The old bare and outlined variants are removed. Missing-content placeholders, such as an absent portrait, remain separate.

Rendered checks passed in both game themes.

## comment 5470549432 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/56#issuecomment-5470549432

Created: 2026-08-30T18:41:09Z; updated: 2026-08-30T18:41:09Z

Exact metadata: [source record](sources/comment-5470549432-55cf4c909f8ab6a074b07b100674dca6fb646979c808c7dbdbad7a49c8e9caf3.json).

FF8 Use Flags now treats each checkbox, label, and filled help marker as one responsive unit. Labels truncate before they can overlap the next control. Encounter Formation uses the same help control for its four values.

## comment 5473538317 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/56#issuecomment-5473538317

Created: 2026-08-31T04:03:31Z; updated: 2026-08-31T04:03:31Z

Exact metadata: [source record](sources/comment-5473538317-e895cbffdb3b5ba46cefb1428943b2367c672bf57881b541484fdcc36964b2f1.json).

The question-mark control now opens a custom themed popup immediately on hover or focus. It no longer uses the delayed browser tooltip. Rendered FF8 and RDR2 checks passed.

## comment 5473982860 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/56#issuecomment-5473982860

Created: 2026-08-31T05:06:12Z; updated: 2026-08-31T05:06:12Z

Exact metadata: [source record](sources/comment-5473982860-db0d7ad13affe34a4a84c77e44b2cb8175207c49c3ff76e0b2b4a375274e7791.json).

FF8 help markers now have one enforced game-themed state: white circle, black FF8-font question mark, and red hover/focus state. This removes the grey marker variants that survived through section inheritance.

## comment 5550274021 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/56#issuecomment-5550274021

Created: 2026-09-05T07:25:03Z; updated: 2026-09-05T07:25:03Z

Exact metadata: [source record](sources/comment-5550274021-c604e6ec2935a550842e81457bb41f9fe146e9a640f245ab62702457ec2b87af.json).

Reopened after the reported Blank regression. Shared field help is now 18 pixels, centered in the metadata slot, and uses a normal pointer so the cursor does not cover the question mark. Hover replaces the type text with the help marker. Rendered Blank checks passed at wide and narrow sizes; awaiting your visual check.
