# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286083262 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27

Created: 2026-08-29T10:46:25Z; updated: 2026-09-04T12:55:31Z

Exact metadata: [source record](sources/issue-5286083262-ff3d1e90a31b0605bea4c2a624bab3b158810af86f1f59c68f90ce2232a6de45.json).

The shared shell should own game-independent navigation and mod selection.

- Replace the Data Map question mark with a clear map icon.
- Add a global Info button beside Data Map.
- Remove per-plugin Setup or Project navigation tabs. Their setup/status content opens from Info.
- Use one shared mod-project selector across plugins.
- Keep the active mod name and location in that selector, not duplicated in Info.
- Add Browse and Create New Mod actions.
- Let each plugin define the files required to initialize a valid new mod.
- Keep the shared selector and top-bar tools consistent while themes supply colors and fonts.

Acceptance:
- Every installed plugin shows the same Map, Info, and mod-project controls.
- Map and Info open in the current window and return to the editor.
- No plugin keeps a redundant Setup or Project tab.
- Browse switches to a valid mod and reloads the plugin against that path.
- Create New Mod creates a valid game-specific project and selects it.
- A rendered check confirms icons, layout, and navigation.

## issue 5286083262 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27

Created: 2026-08-29T10:46:25Z; updated: 2026-09-06T13:30:54Z

Exact metadata: [source record](sources/issue-5286083262-80cb6e1f855a1bed086ee522de20d65519b0fa33708f448e392bf0f21cb7806f.json).

**Needs testing.** The latest selector repair is ready for review.

- [ ] Restart Lexeditor. Compare the closed mod selector with its selected dropdown row: name, colored icons and alignment should match.
- [ ] Open Map and Info, then return. Confirm no duplicate Setup/Project tab or lost selection.
- [ ] Create a disposable UI-test mod, then Browse back to your original. Confirm selection works and unsaved-change warnings protect edits. Report the failed step.

## issue 5286083262 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27

Created: 2026-08-29T10:46:25Z; updated: 2026-09-06T13:30:54Z

Exact metadata: [source record](sources/issue-5286083262-b9efb3d5527b183141adfb8069a1547df4a9c516c64104936eedbb039cf84230.json).

**Needs testing.** The latest selector repair is ready for review.

- [ ] Restart Lexeditor. Compare the closed mod selector with its selected dropdown row: name, colored icons and alignment should match.
- [ ] Open Map and Info, then return. Confirm no duplicate Setup/Project tab or lost selection.
- [ ] Create a disposable UI-test mod, then Browse back to your original. Confirm selection works and unsaved-change warnings protect edits. Report the failed step.

## comment 5461948664 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5461948664

Created: 2026-08-29T11:00:17Z; updated: 2026-08-29T11:00:17Z

Exact metadata: [source record](sources/comment-5461948664-6fdc66c7d95a58fa7c12411468eadb777b78757944b6da0eb109355605ec62d0.json).

Implemented the shared shell tools. Data Map now uses a map icon; Info is a global button beside it; Setup/Project tabs are gone; and every plugin uses one mod selector with Browse and Create New Mod. Project changes restart the child service with the selected editable root. The hidden host switch and rendered FF8 check passed.

## comment 5462964910 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5462964910

Created: 2026-08-29T14:28:27Z; updated: 2026-08-29T14:28:27Z

Exact metadata: [source record](sources/comment-5462964910-f1cb2ab6dc8fa5d76397239bb9e311a67ba9975e4762a868ba52345788cd4085.json).

Refine the shared command strip across every game: reserve the first eighth for the padded LEXEDITOR home control; put the mod selector then Save on the left; center Undo and Redo; put Settings, Data Map, and Info on the right. Remove separate project Find/Create buttons and place a split New Mod / Find a Mod action row at the bottom of the selector.

## comment 5462995887 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5462995887

Created: 2026-08-29T14:34:46Z; updated: 2026-08-29T14:34:46Z

Exact metadata: [source record](sources/comment-5462995887-111d9299184569a1b29032e0dc3db208376bc83e0009490fc79e0b239a40e936.json).

The shared strip now uses the requested layout in every game. The mod selector is followed by Save on the left, Undo/Redo stay at the window center, and Settings/Data Map/Info sit on the right. The separate project buttons are gone; open the selector and its last row is split into New Mod and Find a Mod. Please restart Lexeditor and check the strip at your normal size and at its narrowest size.

## comment 5464105649 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5464105649

Created: 2026-08-29T18:25:41Z; updated: 2026-08-29T18:25:41Z

Exact metadata: [source record](sources/comment-5464105649-152dc77ebaa882d1705f42466ff5f9789ccb6ea8c783caf7cc05e3ec14b4ee80.json).

Fixed the FF8 command-row clutter. Routine FFNx readiness text no longer appears below the mod selector. The selector now uses one aligned neutral-font row and a drawn chevron, so no game font can turn it into a stray V.

## comment 5464307945 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5464307945

Created: 2026-08-29T19:09:01Z; updated: 2026-08-29T19:09:01Z

Exact metadata: [source record](sources/comment-5464307945-2abd5696f89c58013bec1e5621b967a1987692d60bd9cdaf52363929859717ac.json).

The height difference came from FF8 retaining the browser's default margins around the LEXEDITOR heading, while the shared shell still allowed a game stylesheet to set its own row height.

The command row is now a shared 48-pixel border-box in every game. The shared frame clears the heading margins, and the contract rejects plugin-owned row heights. Hidden renders measured the same 48-pixel row with no horizontal overflow in FF8 and RDR2.

Please restart Lexeditor and compare the two game modes. Their colors and fonts should still differ, but the command row height must stay the same.

## comment 5470548617 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5470548617

Created: 2026-08-30T18:40:59Z; updated: 2026-08-30T18:40:59Z

Exact metadata: [source record](sources/comment-5470548617-bec4a46abaaeedaf71831a9bc82bfa16fffa9d364038430cc5244f9dc0486801.json).

The FF8 project path in the selector and its menu now uses the FF8 menu font instead of the global Lexend font. The hidden FF8 render confirmed the computed font and no shell errors.

## comment 5471520858 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5471520858

Created: 2026-08-30T22:01:23Z; updated: 2026-08-30T22:01:23Z

Exact metadata: [source record](sources/comment-5471520858-824048154fb8352acbb71792cc212d2e7b0077b3d071ca54c745908cb4f2a631.json).

The shared selector now has per-mod Rename actions and JSON-backed funny name suggestions. The remaining part is the real read-only Vanilla entry and save-to-new-mod handoff. That needs a proven baseline adapter for each plugin; an editable working folder will not be mislabeled as Vanilla.

## comment 5473538358 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5473538358

Created: 2026-08-31T04:03:31Z; updated: 2026-08-31T04:03:31Z

Exact metadata: [source record](sources/comment-5473538358-7fc321a99e14acd8945225aa4c090780f09febf43feda1212fa8e80aa15f42a8.json).

Blank now shows the real shared mod selector with My Mod and read-only Vanilla. It does not use a fake disk project or private selector. The broader real-plugin Vanilla-adapter work remains open.

## comment 5473749498 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5473749498

Created: 2026-08-31T04:31:56Z; updated: 2026-08-31T04:31:56Z

Exact metadata: [source record](sources/comment-5473749498-c849227e4f119855b289cc5c62b75f8ba102a801e3648c1a63a07b4c64cb8738.json).

Fixed a real shared-selector race found by the new FF9 plugin. Fast-loading plugins could mount before WebView2 finished exposing the project API, get one null response, and hide the selector forever. The shared control now retries bridge registration and remains usable even before a first mod is selected. The full hidden FF8 → Home → resident FF8 → FF9 switch passed with both project selectors and New Mod / Find a Mod actions present.

## comment 5475134150 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5475134150

Created: 2026-08-31T07:24:13Z; updated: 2026-08-31T07:24:13Z

Exact metadata: [source record](sources/comment-5475134150-370668f4dccf70d5c2093ea524c91d41832f5af45fb0abff610132adad2902a9.json).

Vanilla is now the first entry in every game's shared mod selector. FF8 switches to its extracted unchanged datasets and disables Save; selecting the current mod reloads the editable data. FF7 uses its decoded Vanilla kernel, RDR uses its prepared baseline files, and RDR2 keeps its decoded Vanilla source. Blank uses its packaged baseline; FF9 and Warband show an honest read-only baseline notice where decoding is not complete. Restart Lexeditor, open FF8, and choose Vanilla from the top-left selector to check it.

## comment 5538725097 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5538725097

Created: 2026-09-04T09:49:12Z; updated: 2026-09-04T09:49:12Z

Exact metadata: [source record](sources/comment-5538725097-d512c90c4b4ecce76b7c956b86478b6764b88c9ed38f801ab1b9cabe8756b95c.json).

Revise the shared command strip: each mod row uses only a lock or edit icon plus a check or X, with no Editable mod or Enabled prose. Put Save and Play between Undo and Redo. Give the full left-side span between LEXEDITOR and the centered controls to the mod selector, and constrain its open menu to the selector width.

## comment 5539030231 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5539030231

Created: 2026-09-04T10:17:01Z; updated: 2026-09-04T10:17:01Z

Exact metadata: [source record](sources/comment-5539030231-dabbea147ec7edac4f6ef533de625c532c619a4a419773cbd989bbdaa2be8beb.json).

New command-strip regressions: show the editable project as Lexer's Mod without repeating the game name. Blank also renders duplicate tab-shortcut prompts. Keep shortcut prompts hidden until hover, reserve equal side space in each tab, and allow the label to fit without overlap.

## comment 5539153888 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5539153888

Created: 2026-09-04T10:28:47Z; updated: 2026-09-04T10:28:47Z

Exact metadata: [source record](sources/comment-5539153888-8a0a4ea790c8469b9c62541617b460c8fb97e2e0722ca3c95ef498be2e127331.json).

The shared selector now uses lock/edit and check/X status icons with no duplicate state prose. Save and Play sit between Undo and Redo. The selector fills the available left span, and its open menu cannot grow wider than the closed control. FF8 displays the featured project as Lexer's Mod without changing its package identity. Rendered selector and shared-shell checks pass; other reported command-strip work remains actionable.

## comment 5540733972 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/27#issuecomment-5540733972

Created: 2026-09-04T12:55:31Z; updated: 2026-09-04T12:55:31Z

Exact metadata: [source record](sources/comment-5540733972-232da828e3ae5f361194c89cdcb11fa1249e245689bed3d076eed15af9864376.json).

Fixed the active-mod status mismatch. The closed selector had rebuilt the lock/edit and check/X states as plain text, so it lost the dropdown row's color and alignment. It now uses the same structured icon elements and styling as the open row. The rendered check confirms matching green color and vertical centering in both states.
