# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5295029282 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/70

Created: 2026-08-30T23:50:36Z; updated: 2026-09-04T12:25:03Z

Exact metadata: [source record](sources/issue-5295029282-3b02c00cd38d5d690fcb83d42ec9dba2b15689d3f9d3f4c509349797d1c19adc.json).

Create the initial Final Fantasy IX plugin shell.

Scope:

- Auto-discover the Steam release and its launcher.
- Use the shared Lexeditor shell with an FF9 identity and theme.
- Expose planned editor areas for Items, Abilities, Magic, Weapons, Armor, Accessories, Characters, Enemies, Encounters, Shops, Synthesis, Tweaks, and Settings.
- Provide Info and Data Map screens.
- Keep all parsing and saving disabled until real FF9 formats and paths are resolved.
- Advertise only scaffold and Data Map capabilities.
- Verify managed startup, shutdown, API identity, syntax, host integration, and hidden rendered output.

Acceptance boundary: this issue creates the plugin shell only. It must not claim that FF9 data can be read or saved.


## issue 5295029282 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/70

Created: 2026-08-30T23:50:36Z; updated: 2026-09-06T13:16:57Z

Exact metadata: [source record](sources/issue-5295029282-ecafb933bbc1bd63b33a9df4a3c11759ed075dce4a92b95402d8798f5027b722.json).

**Status: Closed for the initial plugin foundation.** Detection, themed navigation, Info and Data Map exist, followed by the first typed gameplay-data editors. Complete data coverage and in-game application remain in #74.

## comment 5472049094 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/70#issuecomment-5472049094

Created: 2026-08-30T23:54:31Z; updated: 2026-08-30T23:54:31Z

Exact metadata: [source record](sources/comment-5472049094-3c15d8e66c2eb4fa5cad54a95660c501c5566902f996976d020735b0c445d0f6.json).

Added the initial FF9 plugin shell. Lexeditor now finds Steam app 377840 through its manifest, validates FF9_Launcher.exe, and opens an FF9-themed shared editor with Abilities, Accessories, Armor, Characters, Encounters, Enemies, Items, Magic, Shops, Synthesis, Tweaks, Weapons, Settings, Info, and Data Map destinations. The plugin clearly marks every data area as not integrated, disables Save, and rejects write requests because no FF9 parser exists yet. Managed startup and shutdown, plugin identity, automatic install detection, host navigation, Data Map, and the hidden rendered screen passed.

## comment 5473676996 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/70#issuecomment-5473676996

Created: 2026-08-31T04:21:42Z; updated: 2026-08-31T04:21:42Z

Exact metadata: [source record](sources/comment-5473676996-65bdd7d58102387d8a0084e930788dd633ac6ca449b6de28e4d3dd18a40254e6.json).

The FF9 plugin now has a real, format-aware editor path instead of a scaffold. It reads Memoria/Hades CSV exports for items, item effects, weapons, armor, support abilities, battle actions, character base stats, shops, and synthesis; uses shared Table + Detail views; validates stored scalar types; and saves only atomic project overlays under StreamingAssets/Data. The installed Steam copy is build 5378074 and contains only vanilla p0data containers, with no Memoria/Hades CSV export, so its records are not yet editable. Lexeditor leaves those containers untouched and reports the missing export clearly. Enemies, encounters, direct p0data extraction, and in-game acceptance remain open.

## comment 5473713707 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/70#issuecomment-5473713707

Created: 2026-08-31T04:27:00Z; updated: 2026-08-31T04:27:00Z

Exact metadata: [source record](sources/comment-5473713707-60accae7c5110c79e0503aee050685207a29aeedb5ece74ae5523a6985a353e7.json).

FF9 now uses Lexeditor's shared mod-project manager. **New Mod** creates a valid StreamingAssets/Data project from the packaged starter, **Find a Mod** validates the same Memoria layout, and project switches restart the FF9 service with the selected path. Auto-discovery, FF9 checks and smoke tests, project creation, the hidden rendered editor, and the full hidden FF8-to-FF9 host switch passed. The remaining p0data, enemy, encounter, runtime, and in-game boundaries are unchanged.

## comment 5476219865 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/70#issuecomment-5476219865

Created: 2026-08-31T09:10:41Z; updated: 2026-08-31T09:10:41Z

Exact metadata: [source record](sources/comment-5476219865-e2fcb2c6fd49ea176b1609ecd1bb6780cd17ae59f6cab89e4dcf4cef3c46d006.json).

The FF9 plugin now meets this issue's scaffold-only contract. Steam discovery, FF9 identity, shared navigation, Info/Data Map, managed startup and shutdown, host discovery, and hidden rendering all pass. The later direct p0data*.bin work is outside #70's stated scope and no longer keeps this issue actionable. Please review the FF9 entry and its editor shell; installed-game container editing remains a separate boundary.


## comment 5486972016 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/70#issuecomment-5486972016

Created: 2026-09-01T01:04:04Z; updated: 2026-09-01T01:04:04Z

Exact metadata: [source record](sources/comment-5486972016-c9b6ae8b66526833be13b4b71f344fd14660cbb1c3491682ef42d15c5f196936.json).

A clean Steam install no longer leaves Items unavailable. Lexeditor now obtains the pinned official Memoria vanilla CSV baseline, verifies every file before use, keeps it in the private game-data cache, and preserves each file's UTF-8 or Windows-1252 encoding in project overlays. The current implemented datasets load 256 items, 88 weapons, 136 armor rows, 32 item effects, 64 support abilities, 192 battle actions, 12 character base-stat rows, 32 shops, and 64 synthesis recipes. This does not make the FF9 editor complete; the remaining data and runtime work is tracked separately and stays actionable.
