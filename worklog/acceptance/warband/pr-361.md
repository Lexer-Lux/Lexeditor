# Warband acceptance — PR #361

Use an updated normal Lexeditor checkout containing merged PR #361. These are
Python/JavaScript changes: no native driver or mod rebuild is required. Do not
switch another agent's working tree onto the old feature branch.

Double-click `tools/Warband-checks.cmd`. It uses Lexeditor's existing Python
installation, runs the supplied disposable checks, saves a report in the Windows
temporary folder, then opens the Warband editor. Temporary test windows may appear;
it does not start the actual game or edit your module, game assets or saves.
`--checks-only` suppresses opening the editor. The ordinary `Lexeditor.cmd` and
existing desktop shortcut also use the updated code after restart.

## Installed-game checks

- **Items (#20/#78):** Select ankle boots, a helmet, a sword and a long polearm.
  Each heading has a lit, fully framed still icon. Open the larger preview,
  rotate/zoom, close/reopen, and change items/tabs; no stale model should remain.
  Check tab lettering, shortcut badges and Information > Mod Manuals. Browse
  during first icon generation, restart, and revisit items; report missing icons,
  bad framing, stalls, unreadable text or repeat generation. The automated fixture
  already changes a temporary DDS and checks pixel regeneration/module isolation;
  do not modify your installed textures just to test cache invalidation.
- **Troop Trees (#96):** Select a Warband source mod. Switch faction and tree;
  select a root, both branches and an end troop. Roots sit below upgrades and
  every selection shows matching right-side details. Resize and scroll wide trees.
- **Play (#97):** With a built module installed under the selected game's Modules
  folder, press Play, confirm that module's menu and load a save, then Stop. Use
  stock Warband on an installation without WSE2; WSE2 is selected when installed.
  Stop must close only the launched session. A launch error must restore Play and
  explain the failure. Real Warband/Steam/WSE2 sessions are not established by CI.
- **Data Maps (#98):** In Warband and your other installed plugins, open Map,
  filter/sort/page, resize and follow interface links. Whole rows and the bottom
  pager must remain visible. Warband skills are Source only, not a structured
  editor; missing sources cannot claim editable coverage. Close source views
  without saving. Partial rows state their actual editable subset.

Report the issue number, module/item/troop IDs, screenshot and visible error.
For launch failures include executable/version and the relevant game log.
The diagnostic report is a fixture result, not a substitute for these checks.
