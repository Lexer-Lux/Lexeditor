# #98: Make Data Map coverage honest and paging consistent

## Sources and requirements

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/98), [implementation session](github-98/implementation-2026-09-06.md) remain preserved. Distinguish source-only, read-only and structured editable interfaces; reserve implemented claims for the actual user-facing capability and link to that interface. Raw file I/O is not a structured editor. Use the same shared fitted paging controls as Blank, without clipped final rows or master-list scrolling. Audit the same claims/layouts across all plugins, not only Warband.

## Delivered implementation and evidence

PR #361 merged to master as bc6f97ef456b0a20b08358612c26eb400c97d2e7. All seven UI implementations, including the two FF7 editions that share an implementation, use the shared fitted Data Map. Explicit capability boundaries and per-dataset/subview links are documented in `codex/shared/data-map-coverage.md`. Preserved binary layers and inactive runtime controls do not claim structured editing.

CI run 34040197660 passed seven coverage tests on Windows/Linux and 24 rendered plugin/size cases including Warband. Fixtures exercise filtering, stable paging, available interface links and missing/source-only boundaries at 900x620, 1200x800 and 1600x1000. Narrow RDR2 and Warband screenshots were inspected. In-memory boot fixtures do not establish installed-game data coverage or deployment.

## Remaining acceptance

In the normal updated master checkout, follow Data Maps in `docs/warband-acceptance.md`: open each installed plugin's Map, filter/sort/page/resize and follow the available interface links. Warband skills must be Source only; missing files must not claim an editable interface. Notes may scroll in the detail pane, while list rows and the bottom pager stay fitted. Close source views without saving. Report plugin, source row, screenshot and incorrect destination/claim. The cross-plugin development audit is complete; actual installed-editor acceptance remains. No new design answer or code build is needed.


## PR #489 Warband completion audit — 2026-09-19

PR #489 (codex/warband-plugin-completion) now preserves the modular Warband UI and plugin contracts from master 72ee978a2ff36686a6349696b19860057356468a as a merge parent.

- [x] Raw Module System source presence no longer counts as partial integration.
- [x] Skills, quests, strings, source info pages, music, sounds, meshes, factions and post-processing use a shared Misc. Table + Detail editor backed by span-preserving source patches, stale-SHA refusal, duplicate-ID checks, backups and atomic replacement. IDs remain fixed because other Module System files reference them.
- [x] Sea-Monster/WarbandModuleSystem 1.171 at 66c67147692707b85c457db10a112627118733a5 is the MIT-licensed schema/export reference; no upstream code or proprietary game dump is bundled.
- [ ] Remaining documented stable-ID Module System families still need safe scalar/vector subsets audited into Misc. where practical. Scripts, triggers, dialogs and animation operation/sequence logic remain source-only unless represented honestly.
- [ ] Current modular browser acceptance must pass loading/empty/error, paging, Detail/table edits, discard, Save/build and reopen at the three fixture viewport sizes, followed by screenshot inspection.
- [x] WSE2 setup already uses the real bundled pinned package, explicit offline Install/Repair, integrity verification, rollback and read-only upstream checks; its self-updating launcher is excluded and never invoked.
- [ ] Final isolated candidate and human installed-game checklist remain after branch-native checks complete; fixture evidence does not establish Steam/WSE2/game behavior.

Current master provides ui/component-catalog.js and it was reviewed after the concurrent UI refactor. PR #489 introduces no shared component or shared-framework selector.
