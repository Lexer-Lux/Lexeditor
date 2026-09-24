# #479: Split the large plugin pages into modules — CLOSED 2026-09-23

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/479)

## Closure evidence

All six plugin pages split; `editor.html` is a ~1KB loader in each:

- rdr2, ff8 (previously checked).
- ff7 (editor.js 11KB): controls.js, details.js, workspace.js.
- ff7r (editor.js 15KB): tables.js, panels.js, inputs.js, curated.js, economy.js, loot.js, text.js, views.js.
- rdr (editor.js 12KB): items.js, shops.js, missions.js, settings.js, loot.js, datamap.js, project.js.
- warband (editor.js 12KB): items.js, troops.js, troop_editor.js, troop_trees.js, settings.js, datamap.js, dashboard.js, boot.js.

`tools/verify_shared_ui_contract.py` (the shape contract the issue names) passes on
misc-fixes, including the lane-pin alignment to the decided 7.5%. Boxes ticked
with an evidence note; issue closed; `actionable` label removed. Visual
acceptance stays with the plugin issues, never claimed here.
