# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356488488 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/337

Created: 2026-08-24T15:38:07Z; updated: 2026-09-05T07:40:43Z

Exact metadata: [source record](sources/issue-5356488488-f5a1a11b052fe89d71532387bb34a34d5c4a36a6344bdc1743b6aa8556af4dfe.json).

Extend the RDR Lexeditor plugin with Items, Shops, Loot Tables, Missions, Settings, Data Map, and GitHub surfaces like the actual RDR2 plugin. Remove the raw Files tab. Build the Data Map from a generated scan of the real prepared RDR data, with source archive/path, coverage, count, editability, and caveats.

Use the RDR2 list-panel and detail-panel visual structure. Keep identity and editable data rows inside the list-panel view instead of placing a generic form beside it. Use the correct constrained input type for every known field: toggles for booleans, bounded number controls for numeric ranges, and selects for enums. Do not use free text when the data contract supplies valid choices or bounds.

The Settings tab must edit this mod's real configuration. The GitHub surface must target Lexer-Lux/rdr-overhaul. Preserve unsupported fields without loss and never write an installed game archive.

Acceptance: there is no Files tab; the Data Map reflects generated RDR coverage; Items, Shops, Loot Tables, Missions, Settings, and GitHub use real project data; the right panel matches the RDR2 list-detail visual language; constrained inputs replace inappropriate free inputs; saves read back; and installed archives remain unchanged.

## issue 5356488488 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/337

Created: 2026-08-24T15:38:07Z; updated: 2026-09-06T13:26:43Z

Exact metadata: [source record](sources/issue-5356488488-e5fe8d358ed94e9a35a7f62cdbd252edbb107506d72b2fcdb334a71ad206c36d.json).

Provide real Items, Shops, Loot Tables, Missions and Tweaks editing, with honest Data Map coverage and the shared list/detail layout. Do not substitute a raw Files tab or overwrite installed archives.

**Status: Partly implemented.** Items, Shops and Missions have working editor surfaces; remaining data coverage and end-to-end in-game application still need completing. Not ready for overall acceptance.

## comment 5559523872 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/337#issuecomment-5559523872

Created: 2026-09-06T13:26:43Z; updated: 2026-09-06T13:26:43Z

Exact metadata: [source record](sources/comment-5559523872-58596c3e6fae592c84be256309995bc5ae008ad24133aef44663893db6272b56.json).

#362 repairs decimal shop saves, invalid numeric inputs, loot discard and recovery from broken optional JSON. Unit and browser checks pass. This is an editor-only improvement: remaining coverage, native runtime work and in-game deployment are still unfinished, so this issue stays actionable.
