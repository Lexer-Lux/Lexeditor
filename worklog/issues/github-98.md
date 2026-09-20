# #98: Make Data Map coverage honest and paging consistent

## Sources and requirements

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/98), [implementation session](github-98/implementation-2026-09-06.md) remain preserved. Distinguish source-only, read-only and structured editable interfaces; reserve implemented claims for the actual user-facing capability and link to that interface. Raw file I/O is not a structured editor. Use the same shared fitted paging controls as Blank, without clipped final rows or master-list scrolling. Audit the same claims/layouts across all plugins, not only Warband.

## Delivered implementation and evidence

PR #361 merged to master as bc6f97ef456b0a20b08358612c26eb400c97d2e7. All seven UI implementations, including the two FF7 editions that share an implementation, use the shared fitted Data Map. Explicit capability boundaries and per-dataset/subview links are documented in `codex/shared/data-map-coverage.md`. Preserved binary layers and inactive runtime controls do not claim structured editing.

CI run 34040197660 passed seven coverage tests on Windows/Linux and 24 rendered plugin/size cases including Warband. Fixtures exercise filtering, stable paging, available interface links and missing/source-only boundaries at 900x620, 1200x800 and 1600x1000. Narrow RDR2 and Warband screenshots were inspected. In-memory boot fixtures do not establish installed-game data coverage or deployment.

## Remaining acceptance

In the normal updated master checkout, follow Data Maps in `docs/warband-acceptance.md`: open each installed plugin's Map, filter/sort/page/resize and follow the available interface links. Warband skills must be Source only; missing files must not claim an editable interface. Notes may scroll in the detail pane, while list rows and the bottom pager stay fitted. Close source views without saving. Report plugin, source row, screenshot and incorrect destination/claim. The cross-plugin development audit is complete; actual installed-editor acceptance remains. No new design answer or code build is needed.

## Warband completion audit — 2026-09-19

Branch `codex/warband-plugin-completion` began from current master
`a47f0a57f8b44113b0ca1d42e5795f59f707372a`. Live Warband issues #20, #78,
#96, #97, #98 and #365 remain open with no newer issue comments; their existing
implementation/real-game acceptance split is preserved.

Current references read before implementation:
- `AGENTS.md` `ec8d363d7fa9b937c8849dfa4c13c7c0fc5d1fde`
- `docs/ADDING_A_GAME.md` `78a987c5f61d3f28fb6f4195d08717c98dcb2af8`
- `docs/UI-MANUAL.md` `14a3269992031d7e7893fcb127728a48b944e71f`
- Blank gallery `games/blank/editor.html` `cd3c79bab8a5b13b3167a26e8fe4e0617c940802`
- RDR2 Table+Detail reference `games/rdr2/editor.html` `9d11f8a0bd35526dbb4959fd3e964a4f72472718`
- Warband catalog/editor `54fc0775a372593035ff4b9f0facaf9f06826a0b` /
  `2aea0febe944438674ff52e842d652deb219d3f6`
- `codex/warband/README.md` `79bd0de5e99cf86e1c8d0435170528becff70ed7`,
  `module-layout.md` `4f6f0c5678628c0da652984fa6de7e1661e728c0`,
  `managed-wse2.md` `cf232befa360aefb6531f1176d9ccdbbd70841af`
- `worklog/acceptance/warband/pr-361.md`
  `0dd5617c035834809573281cec1f955fc277ae01`

Requested `ui/component-catalog.js` is not present on current master (GitHub
contents lookup returns 404); no replacement path is being invented.

### Requirement / gap / evidence / next work

- [x] **Live state first.** No open Warband plugin PR existed; current master and
  Warband issues/comments were inspected before branching.
- [x] **Coverage claim audit started from code.** `server.data_map_rows()`
  currently calls every present non-special Module System source file
  `source / partial` solely because the generic source textarea can edit it.
  Per the Data Map contract, raw/source editing is not structured integration.
- [x] **Existing implemented boundaries preserved.** Settings and Items are
  structured; Troops is a deliberately partial structured editor; BRF/DDS are
  read-only item-preview dependencies; generated text and SCO/other binary
  groups are not being relabeled as structured.
- [x] **Public schema source verified before parser work.** Sea-Monster's
  `WarbandModuleSystem` commit
  `66c67147692707b85c457db10a112627118733a5` is MIT licensed. Its Module
  System 1.171 source and process files document fixed record schemas for
  skills, quests, factions, strings, info pages, meshes, music and sounds.
  This is used as format/schema reference only; no proprietary game dump is
  copied.
- [ ] **Implement safe structured families.** Add span-preserving, stale-write
  checked editors and synthetic round-trip tests for the simple documented
  record families that can be represented honestly with semantic controls.
- [ ] **Audit complex families individually.** Scripts/triggers/dialogs/menus,
  mission templates, presentations/tableau, parties/scenes/props, skins,
  animations and particle data remain source-only until a bounded dedicated
  screen can preserve their nested semantics. Presence of a source file alone
  will no longer be described as integration.
- [ ] **Rendered evidence.** Exercise loading/empty/error, filter/page/select,
  edit/discard/save/reopen and Data Map navigation in the plugin-scoped
  headless browser fixture at the existing desktop/narrow/large sizes; inspect
  its screenshots.
- [ ] **Delivery evidence.** Run branch-native Warband source/browser checks and
  produce the isolated candidate/acceptance steps without touching
  `C:/Lexeditor` or an installed module. Real installed assets, WSE2/Steam,
  launch, and in-game behavior remain separate human acceptance.

