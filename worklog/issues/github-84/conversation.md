# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5346645364 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/84

Created: 2026-09-04T09:49:11Z; updated: 2026-09-04T12:25:14Z

Exact metadata: [source record](sources/issue-5346645364-b1a29432fcea5aca564796d14e7dffc3108905972151b4ddf40d40de1506704e.json).

Build a coverage matrix against the installed Deling and Ifrit source trees, then close every supported-data gap in the FF8 plugin.

Acceptance requirements:
- Combine the current Fields and World Map views under one Maps tab with Field and World subtabs.
- Render the actual FF8 world map and expose Deling-equivalent world-map editing, not only the decoded record lists.
- Match Deling's editable FF8 field, world, archive, text, model, texture, script, walkmesh, encounter, and related data coverage where the installed 2013 game supplies the data.
- Add Ifrit-equivalent enemy AI source editing and the rest of its supported enemy data.
- Preserve unknown bytes and round-trip unchanged files exactly.
- Reuse upstream algorithms or code only when the source license permits it; record attribution and the exact primary source files used.
- For every slice, prove corpus parsing, unchanged identity, a controlled mutation, save/readback, and rendered UI behavior.
- Do not claim parity from tab names or inventory rows. Keep unsupported items explicit until they have real controls and save paths.

## issue 5346645364 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/84

Created: 2026-09-04T09:49:11Z; updated: 2026-09-06T12:45:51Z

Exact metadata: [source record](sources/issue-5346645364-f0298291befbbcdba3fb8ea90e870c97b9bf275059287e04d1207ade49b2c77d.json).

Maps now combines Field and World, but Deling/Ifrit-equivalent coverage is incomplete.

**Work remains:** fix misplaced world markers and missing Draw Point map imagery; add the requested textured 3D toggle, 4×4 palette controls and field-local detail tabs; finish verified enemy-AI editing. Preserve unknown data and confirm real save/runtime behavior, not just the presence of tabs.

## comment 5538942207 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/84#issuecomment-5538942207

Created: 2026-09-04T10:09:27Z; updated: 2026-09-04T10:09:27Z

Exact metadata: [source record](sources/comment-5538942207-26b5c0b05b68b4e3c2253236663ea8c9baff85d95e378af3938f287589847105.json).

The World Map tab now has an actual map view from the installed FF8 map asset, aligned to the game's 32 by 24 WMX segment grid. You can select a visible segment, inspect its 16 geometry blocks, and edit its proved WMX group ID and encounter region. The full installed WMX corpus round-trips exactly outside the edited bytes, the map saves through the normal Save button, and separate mod edits to different segment groups compose by priority. The remaining Deling work includes its textured 3D mesh, camera rotation and alternate-segment filters, plus the wider field/archive/model parity, so this issue remains actionable.

## comment 5539086707 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/84#issuecomment-5539086707

Created: 2026-09-04T10:22:38Z; updated: 2026-09-04T10:22:38Z

Exact metadata: [source record](sources/comment-5539086707-6010144d5b47b83362c6cd8e74b32716f3d787ad3a7ca95066fe5c3f51da83b2.json).

Field and World Map now share one top-level Maps tab with Field and World subtabs. World keeps its nine data subtabs underneath. Rendered checks switched between the combined views, kept the outer tabs through rerenders, selected map cells, edited a segment, and saved it. Deling parity remains actionable.

## comment 5539252422 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/84#issuecomment-5539252422

Created: 2026-09-04T10:38:34Z; updated: 2026-09-04T10:38:34Z

Exact metadata: [source record](sources/comment-5539252422-3f7ac9894bdf0bb38b8ec9b446cb4dfdaf25b71f6015bcd264d285d9bc7ed0f3.json).

Feature freeze for triage. New world and field reports:

- World-map marker coordinates currently collapse toward the top instead of aligning with the displayed map.
- Draw Points shows the coordinate grid but no map image.
- Keep the current 2D map view and add a corner control that switches to a Deling-style textured 3D model view.
- Replace World Textures palette preview controls with a numbered 4 by 4 button grid.
- Field should use a simple table on the left and a tabbed field-detail panel on the right. Include Camera, Walkmesh, Exits, Doors, Camera Ranges, Movie Camera, Miscellaneous, and every other field-local Deling resource that applies, including text, sounds, scripts, models, and encounters. Keep separate whole-game browsers such as SFX; the Field views are filtered slices for the selected field.

Do not implement these additions until Lexer triages them.
