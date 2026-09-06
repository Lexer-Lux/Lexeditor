# Reviewed issue rewrites — editor and shared UI

Each @@ header is issue number | workflow | title. Original bodies are preserved by the apply audit before replacement. Historical comments are not edited.

@@ 5|untested|Compare effects, tags and rewards with reference mods
Effects, Tags and Challenge Rewards now show per-entry reference matches and separate reference-only entries. The latest layout and picker repairs need a visual check.

- [ ] Restart Lexeditor. In a test RDR2 mod, add/remove an Item Effect or Tag; confirm its reference marks update and missing reference entries appear below the divider. Undo the edit.
- [ ] Open Challenges and change a reward. Confirm the same reference layout works and Add stays below the complete list. Report a mismatched row or screenshot.

@@ 6|untested|Edit an item's quick-select slots
Items now supports multiple quick-select assignments with valid slot dropdowns, add/remove, undo and saving. Editor checks passed; your check remains.

- [ ] Restart Lexeditor and use a test RDR2 mod. Open an item's Quick-select slots, add a permitted slot, then remove it; duplicate slots must be refused.
- [ ] Save an assignment change and reopen the item. Confirm every assignment is retained and other items are unchanged; report the item and failed step.

@@ 7|untested|Restore the colored Save icon and readable game fonts
The colored floppy-disk icon and RDR2 font hierarchy are restored. Text metrics were also adjusted; appearance needs your check.

- [ ] Restart Lexeditor and open RDR2. Check Save, main tabs, item names and descriptions: the floppy should be colored, headings use the display font, and smaller text remain readable.
- [ ] Resize the window and inspect the bottom list row for clipping. Send a screenshot of any wrong font or alignment.

@@ 8|untested|Tidy the Items list, heading and toolbar
Items now has separate identity columns, a larger name/icon, centered Add, right-aligned filters, and stacked lookup/preview buttons. Rendered checks passed.

- [ ] Restart Lexeditor and open RDR2 Items. Check Name/Item, ID, Group and Category columns, the full-width heading, and the lookup button above the preview eye.
- [ ] Search, filter and select several items, then narrow the window. Confirm names and icons are not clipped and the controls do not overlap; report the affected item or control.

@@ 9|untested|Use one consistent Add button
Create/add controls now use the shared icon-only plus button with an action tooltip. RDR2's plus glyph and empty Recipe control were corrected.

- [ ] Restart Lexeditor. In a test RDR2 mod, compare Add in Items, Effects, Tags and Recipes; each should show the same centered plus and a specific tooltip.
- [ ] Add an entry, then undo it. Confirm the intended entry is created without changing unrelated data; report the failing control.

@@ 10|untested|Resize list and detail panels consistently
The shared divider now supports dragging, keyboard resizing, saved widths and reset. Crafting also uses the common list instead of its former custom table.

- [ ] Restart Lexeditor. Drag the divider in Items, Crafting and Loot Tables; confirm both panels resize without clipped rows or broken paging.
- [ ] Reopen each view and confirm its width is remembered. Focus the divider and use arrow keys; double-click to reset. Report a view that behaves differently.

@@ 11|untested|Make the whole table heading sort its column
Sortable list/detail tables are implemented. The latest repair makes empty space in a heading clickable, not just its small sort icon.

- [ ] Restart Lexeditor. In FF8 Items, click the Name heading away from its icon twice; rows should reverse order each time and the pointer stay intact.
- [ ] Repeat in Magic, Weapons and an editable nested table. Confirm dragging a column or using its help/pin does not accidentally sort; report the heading that fails.

@@ 12|untested|Join the active tab to its subtab strip
RDR2's active main tab and full subtab row now form one continuous red surface, with a clear underline on the active subtab.

- [ ] Restart Lexeditor. Open RDR2 Effects and switch between Effects and Behavior IDs, then check Crafting.
- [ ] Confirm the red surface has no seam or separate subtab boxes, and hover/focus remain visible. Send a screenshot of any mismatch.

@@ 13|untested|Fit and align table columns to their contents
Shared tables now center ordinary cells, keep metadata compact and give names the remaining width. Data Map retains readable left-aligned prose.

- [ ] Restart Lexeditor. Open RDR2 Loot Tables and narrow its list pane; a long value such as ContinuousLinear should remain readable while names shorten first.
- [ ] Sort and change pages. Confirm headings stay aligned with rows and no horizontal scrollbar appears; report a clipped column.

@@ 14|actionable|Show all four issue statuses in the embedded GitHub workspace
The three-panel GitHub workspace exists, with issue editing, comments and priority controls. Its old three-status design merged human decisions and testing into Waiting.

**Work remains:** expose Actionable, Waiting, Needs Testing and Unfeasible separately, using the definitions in AGENTS.md. Needs Testing uses the existing `untested` label. Preserve owner-only access, unsaved game edits and existing issue controls.

@@ 15|untested|Improve the Shops selector and stock tabs
Shop names/counts are centered and more readable. Stock-category rows now share the available width instead of scrolling sideways.

- [ ] Restart Lexeditor and open RDR2 Shops. Check the center list's name/count alignment and “X+ buys · Y sells” summaries.
- [ ] Switch shops and stock categories at wide and narrow sizes. Confirm the two SELLS tab rows remain evenly spaced and readable; send a screenshot of a mismatch.

@@ 16|untested|Prepare RDR2 editor data without a separate developer checkout
First-start preparation now uses the bundled converter. Clean-cache checks passed for the required data; your normal-install check remains.

- [ ] Restart Lexeditor and rescan RDR2. Confirm preparation finishes at Ready without requesting OpenIV or a developer checkout.
- [ ] Open Items, Quick Select, Loot, Challenges, Crime, Dispatch, Weapons and Mobs. Confirm Vanilla data loads; report the first failing page and its error text.

@@ 18|untested|Replace ineffective mob assignments with real archetype editing
Mobs now opens real Combat Profiles and Health archetypes. Unused model-assignment controls were removed; Observed Models is read-only. Typed controls need your check.

- [ ] Restart Lexeditor. Open RDR2 Mobs → Archetypes → Combat Profiles and Health; confirm real values and appropriate number, checkbox and choice controls appear.
- [ ] In a test mod, change one value, save and reopen it. Confirm the edit survives and no model-assignment control claims to affect the game; report the field that fails.

@@ 19|untested|Keep RDR1 lists beside their detail panels
Items uses the shared side-by-side layout. Items, Shops and Missions now reduce row counts before the window clips an entry.

- [ ] Restart Lexeditor and open RDR1 Items, Shops and Missions. Confirm list left, details right, with no unused right half.
- [ ] Resize from a large window to 1280×720 and back. Confirm complete bottom rows and usable dividers; send the page and screenshot for any clipping.

@@ 20|untested|Fit Warband item previews and preserve the game font
Item meshes and the installed font atlas are supported. The latest repair fits previews inside the heading and centers shortcut badges; cached still-image icons remain #78.

- [ ] Restart Lexeditor and open Warband Items → ankle boots. Confirm the entire heading preview fits and the larger preview rotates/zooms.
- [ ] Check tab lettering, shortcut badges and Information → Mod Manuals. Report clipping or damaged text. Item-property editing is not part of this preview implementation.

@@ 21|actionable|Finish and validate FF8 plugin coverage
The FF8 editor exists; this is no longer an unstarted plugin request. Editing, startup and some save-loading paths work, but complete gameplay acceptance remains outstanding.

**Work remains:** finish the missing runtime/features in #31, #84, #91, #93, #100 and #308–#328, then prepare concrete checks for Draw, Refine recipes and text overrides. Do not mark the whole plugin ready because individual tabs or patches exist.

@@ 22|untested|Check the box-art main menu and window controls
Home now uses box-art tiles with compact status, hover details and corner controls. Its latest window-button repair needs a visual check; broken loading quotes are separate in #353.

- [ ] Restart Lexeditor. Confirm tiles have one clear status indicator, useful hover details and working open/locate controls.
- [ ] Check Minimize, Maximize and Close are visible bordered buttons. Narrow the window and report any overlapping title, badge or corner control.

@@ 23|untested|Check shared settings, FFNx status and sound volume
Shared settings and FFNx management are implemented. Helpers remain pinned; update checks must preserve configuration and offline access. The last repair makes volume changes apply live.

- [ ] Restart Lexeditor, change the update-check interval, save and reopen Settings; confirm it persists. Open FF8 Information and confirm an installed FFNx version and result are shown.
- [ ] Change sound volume, then set it to zero; subsequent menu actions should change volume immediately and then be silent. Report a setting that fails to persist or apply.

@@ 25|untested|Keep tab ordering, record headings and pagers consistent
Shared presentation is implemented: alphabetical ordinary tabs, Tweaks last, compact record identity and fitted list rows. Blank exercises the same paged controls.

- [ ] Restart Lexeditor. Open Blank → 2 Panels and a game Items page; resize and page through records. Confirm no clipped last row, duplicate totals or list scrollbar.
- [ ] Check IDs are not repeated as extra fields and Tweaks stays last. Report the page with incorrect ordering or pager text.

@@ 26|untested|Show useful Vanilla references and file locations
Shared reference controls are in place. Data Map now reveals available source files/folders; ordinary RDR2 pages no longer repeat source-file banners.

- [ ] Restart Lexeditor. In a test RDR1 mod, change an item, shop value and mission reward; confirm a Vanilla reference appears and restores each value when clicked.
- [ ] Use a Data Map file-location button in RDR1, RDR2 and FF8. Confirm it reveals the relevant file/folder or gives an explicit missing-file error; report a wrong destination.

@@ 27|actionable|Finish the shared mod selector and command strip
Map, Information and mod selection are implemented; the latest repair aligns the selected mod's status icons with its dropdown row.

**Work remains:** reconcile the remaining command-strip reports, including duplicate shortcut prompts and tab-label fitting. Preserve Browse/Create Mod, guarded switching, and the name “Lexer's Mod” without repeating the game name. A fixed status icon does not complete the wider layout request.

@@ 28|untested|Check units, field references and sliders
Units now sit inside the field border. The latest shared repair aligns references, rotates type labels correctly and makes slider dragging smoother.

- [ ] Restart Lexeditor. Check FF8 Items prices and Blank's field examples: G/× units should remain inside borders, with aligned references and readable type/range text.
- [ ] Drag and release a slider, then edit a number with the keyboard. Confirm the final value stays correct and controls do not jump; report the field and screenshot.

@@ 29|untested|Check Developer and Lexer mode controls
Developer/Lexer controls are implemented. Home Restart now restarts Lexeditor even without a resident plugin; dirty work must still be protected.

- [ ] Restart Lexeditor. Toggle Developer Mode and confirm Restart appears/disappears; use it once with no plugin open.
- [ ] Make an unsaved test edit and restart: confirm you can save, discard or cancel. With the authorized Lexer account, enable Lexer Mode and confirm Blank appears. Report a missing control or lost edit.

@@ 30|untested|Stop helper command windows flashing
Owned helper processes now run without visible console windows while retaining error reporting.

- [ ] Restart Lexeditor and open/rescan an installed game. Confirm no command-prompt window flashes during preparation.
- [ ] Exercise RDR2 search or Warband validation/build and report which action still opens a console, including any displayed error.

@@ 31|actionable|Finish the Formulae Rework
Provide the requested melee, magic, status, healing and accuracy formulas as one editable, per-mod rework with live previews.

**Incomplete:** healing and accuracy have runtime patches; melee, ordinary magic damage and status infliction do not. The Formulae page also has an unresolved scrolling report. Resolve the remaining rule details and deliver the full feature; a preview is not an applied game change.

@@ 32|actionable|Finish the GF layout and shared graphs
The GF selector, signed Compatibility values and three-panel layout are implemented.

**Work remains:** the latest report says GF graphs still use the old layout. Bring them onto the current shared curve controls, keeping Compatibility left, General center and Abilities right. Preserve all 16 GFs, unsaved edits and save/readback behavior.

@@ 33|untested|Show working item icons or a clear unavailable state
The incorrect RDO image path is repaired. Previews now enable only after an image loads; failed icons should not open an empty dialog.

- [ ] Restart Lexeditor. In RDR2 Items, check a Story item and Harrietum: available artwork should load and open normally.
- [ ] Check an item with missing/no artwork. Its preview should be clearly unavailable rather than blank and clickable; report the item name and screenshot.

@@ 34|untested|Make mouse Back and Forward follow editor history
Both mouse navigation buttons now follow visited editor pages. The Lexeditor wordmark returns Home with the unsaved-change guard; resident-plugin behavior is covered by #59.

- [ ] Restart Lexeditor. Browse FF8 Items → Weapons, press physical mouse Back, then Forward. Expect Items, then Weapons—not Home or a new window.
- [ ] Make an unsaved test edit and click the wordmark. Confirm cancellation keeps the edit. Report the button and transition that fail.

@@ 39|actionable|Finish the Enemy editor layout and runtime checks
Enemy stats, rewards and other verified fields are editable, with save/readback support. The tab is not merely a read-only inventory anymore.

**Work remains:** the latest report has curves attached to the wrong side and an unwanted black panel. Restore the intended layout and prepare checks for enemy AI/text changes in game. Wider format coverage remains #84.

@@ 46|actionable|Finish shared panel controls and plugin migrations
The shared panel framework and many migrations are implemented; recent fixes cover metadata, table clipping and divider grips.

**Work remains:** reconcile the outstanding Blank/default-control and tab-layout reports, then verify the remaining migrations. Blank must demonstrate reusable structures without copying FF8's theme. Do not treat the last repaired control as completion of the entire panel redesign.

@@ 49|untested|Restore window movement, resizing and saved size
Native window handling and size persistence are repaired; the real desktop behavior needs your check.

- [ ] Restart Lexeditor, maximize, then restore. Drag the top strip and resize from each edge/corner; the restored window must move/resize, while maximized dragging must not shift it.
- [ ] Close/reopen once restored and once maximized. Confirm the saved state returns onscreen without covering the taskbar; report the failing transition.

@@ 55|untested|Reuse prepared FF8 and RDR1 data on restart
Both warm-cache validators are repaired. Repeated preparation checks reused valid data without extracting again.

- [ ] With FF8 and RDR1 already prepared, fully close and reopen Lexeditor twice without changing their installations.
- [ ] Confirm neither game repeats extraction and both editors still open with data. Report which game shows preparation again and its message.

@@ 56|untested|Keep field help markers centered and readable
The reopened Blank regression has a new shared repair: the help marker is centered and the normal pointer no longer covers it.

- [ ] Restart Lexeditor. Hover fields in Blank and FF8; confirm the question mark replaces type text cleanly and its tooltip is readable.
- [ ] Focus fields by keyboard and narrow the window. Confirm markers stay aligned and visible; send a screenshot of a mismatch.

@@ 59|actionable|Finish resident navigation and loading screens
Keeping a plugin resident, returning through its edge handle and the sticky header are implemented.

**Work remains:** loading quotes have regressed to the fallback message (#353), so the complete loading experience is not accepted. Preserve the live editor and unsaved work across Home/return; returning to a resident plugin must not reload it or replay startup loading.

@@ 60|actionable|Finish stat-curve appearance and live editing
Character stat/XP curves, coefficient editing and live redraw are implemented. HP uses its appropriate larger range, not the original proposed 0–255 axis.

**Work remains:** fix the overlapping graph title/formula and white bar-mode fill; ensure GF graphs share the same layout. The requested larger title must remain clear of the equation. These are implementation fixes, not a request for another design approval.

@@ 68|untested|Save or discard settings without touching other edits
Settings now has its own floppy control and dirty count. A successful save closes the dialog; unrelated game-data edits must remain independent.

- [ ] Restart Lexeditor. Change one setting: expect badge 1; save and reopen to confirm persistence and a cleared badge.
- [ ] With an unrelated Item edit unsaved, change a setting and right-click its floppy to discard. Confirm only that setting reverts and the Item edit remains; report any cross-scope change.

@@ 72|untested|Check game-themed menu sounds
FF8 and FF7 now use extracted game sounds for supported editor actions. FF7's Launch sound remains explicitly unavailable rather than guessed.

- [ ] Restart Lexeditor. In FF8 and FF7, navigate, select, go back and save a test edit; report any missing or inappropriate sound and its action.
- [ ] Turn global Sound off and repeat. Confirm all menu sounds stop, then return when enabled.

@@ 73|actionable|Edit FFNx in Tweaks and use Memoria's own settings launcher
Your latest choice replaces the older specification: FF7/FF8 need their own FFNx settings subtabs; FF9's Memoria subtab should direct you to its existing launcher instead of duplicating that editor.

**Work remains:** reconcile the current controls and FF9 Play route with that decision. Keep typed FFNx controls, safe backups and unknown settings intact. You have already supplied the direction; no further approval is needed.

@@ 74|actionable|Finish FF9 data editing beyond the initial tables
Items, effects, equipment, abilities, actions, character stats, shops and synthesis have initial editing support.

**Work remains:** integrate the remaining data, especially enemies/encounters, and prove saved overrides load in game. Data Map must distinguish editable areas from placeholders. Existing tables do not establish complete FF9 support.

@@ 77|actionable|Finish managed Memoria installation
The detection/download/install backend exists, but installation has not been exercised and the install/update controls and update-frequency behavior remain unfinished.

Finish those paths without losing user settings. Follow your later decision in #73: use Memoria's own launcher for FF9 settings rather than recreating its interface. No installation test is ready for you yet.

@@ 78|actionable|Replace live item thumbnails with clear cached icons
Warband's item heading still uses a live 3D thumbnail. Replace it with a well-lit, consistently framed still image of the actual inventory mesh, while retaining the separate interactive preview.

**Not implemented.** Cache icons separately for each module and regenerate affected images when source assets change. Low priority is not a Waiting status.

@@ 79|actionable|Connect the missing FF7 editor tabs to real data
Initial equipment/materia editing exists, but Characters, Enemies, Encounters and other tabs still lack integrated data.

**Work remains:** add verified editors and save/deployment paths, or clearly show what each unsupported area lacks. Preserve separate FF7 product identities and accurate Data Map coverage.

@@ 80|actionable|Add dialogue controls and a clearer battle interface
One optional Improved Interface tweak should add safe text reveal/history/fast-forward, full-width ATB/Trance with HP/MP bars, and a distinct prompt for unbeaten card opponents. Include keyboard equivalents.

**Work remains:** first reuse the capabilities Memoria already provides, then implement the gaps. Dialogue history must not replay scripts or rewards. No completed candidate is ready for your testing.

@@ 81|actionable|Compare pinned, installed and upstream helper versions
Add a read-only Lexer Mode overview showing each managed helper's pinned, installed and latest upstream version, release date and release notes.

**Work remains.** Opening it should check independently of the normal update interval; Check Again refreshes it. Failed lookups must stay visible without hiding other helpers or installing anything.

@@ 83|actionable|Improve Eat targeting and highlight unlearned abilities
Make Eat's target/availability rules avoid unproductive use, and give enemies carrying an unlearned ability a blue glow.

**Not delivered.** Check Memoria's existing eligibility and highlight support before adding code. No implementation result or prepared test justifies a Waiting label.

@@ 84|actionable|Finish map, field and enemy-AI editing coverage
Maps now combines Field and World, but Deling/Ifrit-equivalent coverage is incomplete.

**Work remains:** fix misplaced world markers and missing Draw Point map imagery; add the requested textured 3D toggle, 4×4 palette controls and field-local detail tabs; finish verified enemy-AI editing. Preserve unknown data and confirm real save/runtime behavior, not just the presence of tabs.

@@ 85|actionable|Add readable credits to every plugin
Every plugin needs consistent credits explaining contributions, with links and separate license notices available offline.

**Partly implemented:** FF8 has credits, but link contrast needs repair. The shared presentation, other plugins and completeness checks still need work.

@@ 86|actionable|Keep game research and internal progress in Lexeditor
Lexeditor should own each game's technical codex and per-issue worklogs. Mod repositories should contain their distributable mod content, not duplicated agent research or logs.

**Work remains:** finish migration, create a codex when scaffolding a plugin, and validate that every supported game has one. GitHub issues remain the brief human-facing view, not the internal progress tracker.

@@ 87|actionable|Add the Journal and next-objective menu
Start should open an optional Journal: Main Quest first, active side quests next, locked quests last with start instructions. Cover the requested side quests and show one-time unlock/update/completion notices.

**Not implemented.** Map reliable quest state and preserve editable progression rules, including compatibility with #88. The detailed request already supplies the direction; research and implementation are agent work.

@@ 88|waiting|Choose the open-world progression design
Make FF8 less linear without breaking required characters, vehicles or story events. No concrete progression design has been selected.

- [ ] Choose the initial scope: earlier free travel, selected missions in a different order, or a substantially open world.
- [ ] Describe which locations, vehicles and party members should become available earlier, and which story gates must remain. This is a design decision, not a game test.

@@ 89|actionable|Prepare new rewards for A Dog And Its Bone
Rebalance this side quest's rewards without duplicate payouts or incorrect Journal progress.

**Preparation remains:** document its current stages/rewards and availability, then present replacement options with their intended gameplay role. Your reward choice comes after those options are prepared; there is no useful decision checklist yet.

@@ 90|waiting|Design the full-screen world map menu
Replace the world-map Back action with a full-screen map menu. The contents and interactions are not yet defined.

- [ ] Specify what it should show: locations, quest markers, unexplored areas and any other information you want included.
- [ ] Decide what selecting a location should do and how zoom/navigation should work. This is design work, not a test of an existing menu.

@@ 91|actionable|Finish card creation, deletion and editing
Existing Triple Triad cards now support names, ranks, elements and selection power.

**Incomplete:** creating/deleting card types still needs engine, artwork, deck, reward and save support; existing-card edits also need in-game validation. The current fixed-slot editor does not fulfil the whole request. The artwork/NPC-deck redesign remains #300.

@@ 92|untested|Check flat stat bonuses
The optional Flat Stat Abilities tweak now changes percentage bonuses to fixed points and updates matching names. Its gameplay effect needs confirmation.

- [ ] Restart Lexeditor, enable the tweak, save and launch FF8. On a character below the stat cap, equip Str+20; confirm STR rises by exactly 20 and the name no longer says percent.
- [ ] Unequip it, then disable the tweak and relaunch. Confirm the fixed bonus disappears and normal percentage behavior returns; report before/after values.

@@ 93|actionable|Implement GF spellbooks safely
Give each GF an ordered, editable spellbook with pages, visible zero-stock spells and optional learned-ability requirements.

**Not delivered:** the draft used an unsafe memory region, was disabled and was not installed. Safe runtime storage and editor integration remain unfinished. There is no spellbook build for you to test yet.

@@ 94|actionable|Finish configurable spell stock and Shared Magic compatibility
A 1–255 cap and the above-127 stock repair are implemented. Full stacks should retain vanilla maximum junction strength at any chosen cap.

**Work remains:** Shared Magic is blocked with non-100 caps pending safe migration, and high-stock casting still needs a prepared game check. The original request includes that combination; the standalone cap is only a partial delivery.

@@ 95|untested|Check ability-category icons
Ability names now include their native category icons in all seven ability tables, headings and GF selectors.

- [ ] Restart Lexeditor and open FF8 Abilities. Check all seven categories and their detail headings for the correct, readable icon.
- [ ] Open a GF ability selector and compare the same ability. Report a missing or inconsistent icon by ability name.

@@ 96|actionable|Show bottom-up troop trees by faction
Replace the flat upgrade list with clickable trees grouped by faction and tree. Selecting a troop must open its details on the right and preserve all upgrade branches.

**Not implemented.** The design is already specified; a prior priority deferral is not a blocker requiring another answer from you.

@@ 97|actionable|Make Play actually launch Warband
Play currently changes to Stop without opening a playable game.

**Needs repair:** check the selected executable, required launch arguments and process handoff. Success must mean a usable game window; failures must restore Play and explain the error. No repaired launch is ready to test.

@@ 98|actionable|Make Data Map coverage honest and paging consistent
Warband calls source-only areas integrated despite lacking structured editors; Data Map paging also differs from Blank.

**Needs repair:** distinguish source-only, read-only and editable coverage, link each claim to its real interface, and use the shared fitted pager. Audit other plugins for the same overstatement. This is development work, not a question for you.

@@ 99|actionable|Prepare a shared UI redesign proposal
Review the menu bar, mod selector, main editing controls and placement of previews. Keep circular utility buttons grouped near the window controls.

**Proposal not prepared.** Present concrete alternatives before asking you to choose; the absence of an agent-produced proposal must not be labeled Waiting.

@@ 100|actionable|Finish record-based mod combining
Independent edits from enabled mods should coexist; later mods should win conflicts according to load order.

**Work remains:** prepare a small, repeatable multi-mod setup and verify the resulting game behavior. You should receive the test mods, exact steps and expected values—not be asked to invent the test.
