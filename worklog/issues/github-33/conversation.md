# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286217527 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/33

Created: 2026-08-29T11:16:06Z; updated: 2026-09-04T12:24:43Z

Exact metadata: [source record](sources/issue-5286217527-bd821d4b41947facbc75b60a89d12e87474365361e36f60e6f586cf04dc3c891.json).

RDR2 Online item inventory icons can resolve to missing remote images. The item detail currently shows an empty icon button, and clicking it opens a dialog containing the browser's broken-image glyph.

Required behavior:
- Resolve the correct image source for RDO dictionaries such as INVENTORY_ITEMS_MP, including CONSOMABLE_HERB_HARRIETUM and other affected entries.
- Determine preview availability before enabling the icon button when practical. Do not make the user open a dialog to discover a known failure.
- When no valid image source exists, show one explicit broken-image state in the item detail itself. Do not show a blank clickable preview.
- The dialog must open only for an image that loaded successfully, or present an intentional error state rather than raw alt text and a browser broken-image glyph.
- Preserve valid Story, MP, satchel, and custom item icons.

Acceptance:
- Test a valid Story icon, valid RDO icon, missing RDO icon, and item with no texture declaration.
- Render the detail states and the valid preview dialog.

## issue 5286217527 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/33

Created: 2026-08-29T11:16:06Z; updated: 2026-09-06T12:45:23Z

Exact metadata: [source record](sources/issue-5286217527-b405a2cdb100448b3ec7f55cece1b2040eee64d348e33ed3e758e04a94405b3b.json).

The incorrect RDO image path is repaired. Previews now enable only after an image loads; failed icons should not open an empty dialog.

- [ ] Restart Lexeditor. In RDR2 Items, check a Story item and Harrietum: available artwork should load and open normally.
- [ ] Check an item with missing/no artwork. Its preview should be clearly unavailable rather than blank and clickable; report the item name and screenshot.

## comment 5462089151 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/33#issuecomment-5462089151

Created: 2026-08-29T11:25:35Z; updated: 2026-08-29T11:25:35Z

Exact metadata: [source record](sources/comment-5462089151-0329606ea77b153cb9e008d65ed5276be746a762f0be3979fd578d083fb762b9.json).

The RDO icon failure came from the wrong Femga directory family: INVENTORY_ITEMS_MP was sent to a path that returned an HTML 404. It now uses ui_textures_mp/inventory_items_mp, including Harrietum. Icon buttons show a throbber while checked, enable only after a real image decodes, and otherwise show a disabled broken-image symbol without opening an empty dialog.
