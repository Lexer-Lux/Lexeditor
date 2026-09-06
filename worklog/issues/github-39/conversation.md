# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286522176 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39

Created: 2026-08-29T12:28:16Z; updated: 2026-09-04T12:24:47Z

Exact metadata: [source record](sources/issue-5286522176-f25df9ab2eccb58e037e7cd8c6bb2cde9ac761e242dd662c8752b054757e2b1c.json).

The FF8 Enemies tab is only a read-only inventory even though first-start extraction already provides the enemy DAT files.

Replace it with a real list-detail editor. The first supported scope must include schema-backed level thresholds, stat curves, rewards, rates, and confirmed enemy properties such as Flying. Use bounded controls and plain labels. Preserve every unedited byte and section in each DAT file. Save project overrides, reload them, and support vanilla and reference comparison through the existing provenance system.

Do not expose guessed fields. Attacks, drops, draws, defenses, and AI can be added only where their binary schema and write path are verified.

Acceptance:
- A listed enemy opens with real editable data, not file size metadata.
- A field change writes only its documented bytes to the project override.
- Save and reload return the changed value.
- Vanilla/reference controls show the corresponding enemy value.
- The standard list-detail layout has no read-only-inventory notice.

## issue 5286522176 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39

Created: 2026-08-29T12:28:16Z; updated: 2026-09-06T12:45:26Z

Exact metadata: [source record](sources/issue-5286522176-8d913df698eace4ef357a2c13d768c101a34818546244d155da91302eb2bd010.json).

Enemy stats, rewards and other verified fields are editable, with save/readback support. The tab is not merely a read-only inventory anymore.

**Work remains:** the latest report has curves attached to the wrong side and an unwanted black panel. Restore the intended layout and prepare checks for enemy AI/text changes in game. Wider format coverage remains #84.

## issue 5286522176 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39

Created: 2026-08-29T12:28:16Z; updated: 2026-09-06T12:45:26Z

Exact metadata: [source record](sources/issue-5286522176-bc938eb527e06a52db76ee9f2583875d76e01132640bc18088a2b0b88e6a76b5.json).

Enemy stats, rewards and other verified fields are editable, with save/readback support. The tab is not merely a read-only inventory anymore.

**Work remains:** the latest report has curves attached to the wrong side and an unwanted black panel. Restore the intended layout and prepare checks for enemy AI/text changes in game. Wider format coverage remains #84.

## comment 5462451555 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5462451555

Created: 2026-08-29T12:36:21Z; updated: 2026-08-29T12:36:21Z

Exact metadata: [source record](sources/comment-5462451555-ec0ba9d61a02d68ccc487e0b15319fa25a5ccce3acc4b5be08c77298f9589e40.json).

The Enemies tab was only a file inventory. It now reads and edits the verified enemy information block: stat curves, level thresholds, XP/AP, Mug and drop rates, and confirmed properties such as Flying, Zombie, hidden HP, and permanent defensive statuses. Saves create a project `direct/battle/c0mNNN.dat` override and preserve every other byte.

Please open an enemy, change one clear value such as AP or Flying, save, then reopen the enemy and confirm the value persists. The Vanilla/reference controls beside each field can compare or restore the source value. Attacks, item tables, defenses, and AI remain hidden until their full write formats are verified.

## comment 5464589655 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5464589655

Created: 2026-08-29T20:01:36Z; updated: 2026-08-29T20:01:36Z

Exact metadata: [source record](sources/comment-5464589655-7d95ccd222b1cfb3addcb62785b3c9455c8bc2de253f5d2d55bd8909e1c67c44.json).

The braces were system-font fallbacks. FF8's menu font does not contain `{` or `}`, but it does contain its own `「` and `」` glyphs. The Enemies list and detail heading now display the two special records as `「Rinoa」` and `「Griever」`. Their source names and saved data remain unchanged.

The rendered check confirms that the full displayed names use the FF8 Menu font.

## comment 5466411167 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5466411167

Created: 2026-08-30T03:12:59Z; updated: 2026-08-30T03:12:59Z

Exact metadata: [source record](sources/comment-5466411167-9fd12f87b4a6ad50f3e18088d1ea68b87e5196e8b295a723ae16ba09165620a9.json).

The structured FF8 data editor now includes all proven enemy tables: 48 ability slots, Draw, Mug, drops, cards, Devour, Renzokuken, and elemental/status defence. Item and Magic references use finder mode. Save and fresh readback checks pass.

The new Encounters tab also edits all 1,024 scene.out formations. Items now expose all four mitem.bin bytes through schema-aware controls.

Enemy DAT remains Partial in the Data Map only because AI bytecode and the executable-embedded Scan text are not yet safe structured editors. I did not guess those fields.

## comment 5466857229 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5466857229

Created: 2026-08-30T05:11:33Z; updated: 2026-08-30T05:11:33Z

Exact metadata: [source record](sources/comment-5466857229-9eeee7f8c83c638328aa79cf91cf58c8edea01d3fad94b5995e6b9115889c9ed.json).

The Enemies detail panel now includes HP, STR, VIT, MAG, SPR, SPD, and EVA curve graphs. They use the documented FF8 equations, label the stored values A–D, and redraw while typing. A hidden render confirmed all seven cards and live provenance.

## comment 5466897484 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5466897484

Created: 2026-08-30T05:22:18Z; updated: 2026-08-30T05:22:18Z

Exact metadata: [source record](sources/comment-5466897484-24f3e8401de60a8cda58f3ecedc2bf2f2cad2a140b4426fbb79bf155b0067568.json).

The Encounter Stage column now has a matching Stage ID pin, so it can be removed and restored from the detail panel. Flags and both camera fields also have matching optional column pins.\n\nThe slot data was present in scene.out; narrow table cells had collapsed the controls. The shared editable-table control now keeps a compact reference lane, and the Encounter table gives signed coordinates enough room. A rendered check shows all four flags, X/Y/Z values, and levels, then unpins Stage successfully. Save and fresh readback also pass.

## comment 5466903185 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5466903185

Created: 2026-08-30T05:23:48Z; updated: 2026-08-30T05:23:48Z

Exact metadata: [source record](sources/comment-5466903185-5ebd45a484677106434ffda537c5d67b016010ad7648bbb8595d9deee78359db.json).

The missing Scan descriptions are unfinished integration, not an engine limit. FF8 stores the vanilla strings in FF8_EN.exe, but FFNx already loads a project-local exe/battle_scans.msd override. Lexeditor can read the vanilla table, expose one description per enemy, and rebuild only that override without modifying the executable. The earlier unsafe-relocation boundary is obsolete.

## comment 5470253399 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5470253399

Created: 2026-08-30T17:41:27Z; updated: 2026-08-30T17:41:27Z

Exact metadata: [source record](sources/comment-5470253399-0f60dc52abaaaae1da1981ecf5a782bc85320a3c517f7c03fa0f5ccc047f6913.json).

Scan descriptions are now editable in the Enemies detail panel. Lexeditor reads all 160 vanilla strings from FF8_EN.exe, maps each enemy by its entity ID, and saves a complete FFNx battle_scans.msd override without modifying the executable. The description has immediate Vanilla/reference restore controls, search support, and an optional table pin. Binary tests changed one description and proved the other 159 stayed equal; temporary save/reload and hidden rendering also passed. The remaining check is to edit one description, save, launch FF8, and confirm Scan shows the new text.

## comment 5470400986 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5470400986

Created: 2026-08-30T18:11:11Z; updated: 2026-08-30T18:11:11Z

Exact metadata: [source record](sources/comment-5470400986-2d16fbabbf4388ca67214050d11b62cf65bd106b1b3fdbafe29582a9fdc7f3a3.json).

Enemy and Encounter sub-tables now sort through the shared Table path. Encounter Finder controls keep one stable width and no inner rectangle. The full enemy, scene.out, mitem.bin, Scan-text, save/readback, and rendered UI checks passed; FF8 was not launched.

## comment 5474810161 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5474810161

Created: 2026-08-31T06:51:10Z; updated: 2026-08-31T06:51:10Z

Exact metadata: [source record](sources/comment-5474810161-3f3cdebde09d93343e9805d092d011d6b1b050070123546e077599a46c374a05.json).

Found the actual cause of the grey Stat Curves question mark: the section heading's grey text stroke was inherited by the nested help marker. Its declared text color was already black, but the inherited stroke covered most of the small glyph. The FF8 help-marker theme now resets that inherited stroke for every header instead of adding a Stat Curves-only exception. Hidden Chromium measures black on white with a zero-pixel stroke; the Enemies render and full FF8 UI render suite pass.

## comment 5482423046 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5482423046

Created: 2026-08-31T18:04:57Z; updated: 2026-08-31T18:04:57Z

Exact metadata: [source record](sources/comment-5482423046-b442688b99394f1d5b53781e80445e8bad6474d61e622935882f9f2e77c42776.json).

Repaired the mangled FF8 Enemies detail view. Scan, compact properties, stat curves, and each editable sub-table now form one vertical scrolling document; the stat section owns its height, so Abilities can no longer draw over the graphs. The rendered view shows readable property controls and four charts per row. Enemy binary, save/readback, live-reference, and rendered editor checks pass. Please restart Lexeditor and inspect an enemy with all extracted data.

## comment 5487505624 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5487505624

Created: 2026-09-01T01:49:07Z; updated: 2026-09-01T01:49:07Z

Exact metadata: [source record](sources/comment-5487505624-31a74ff17cca7d836f6784623c2ae443a7ba975b291273d78cdd9d912a7be780.json).

Repaired the Enemy detail composition and the Encounter enemy-slot state controls. Stat-curve headings no longer collide with the graphs. Encounter Enabled is now the first narrow help-only column; a disabled slot dims and locks every other control in that row. Nested Enemy and Encounter tables still sort after rerendering.

## comment 5539021483 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/39#issuecomment-5539021483

Created: 2026-09-04T10:16:10Z; updated: 2026-09-04T10:16:10Z

Exact metadata: [source record](sources/comment-5539021483-36ad27b376cb7050db3456c40cf90faf626aea57238637b3cc644aabb03d4299.json).

The Enemies curve panel is still attached to the right-side panel instead of the left, and the adjacent panel now has a solid black background. Restore the intended left-side curve layout and the normal FF8 panel surface.
