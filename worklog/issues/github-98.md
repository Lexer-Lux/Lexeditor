# #98: Make Data Map coverage honest and paging consistent

## Sources and requirements

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/98), [implementation session](github-98/implementation-2026-09-06.md) remain preserved. Distinguish source-only, read-only and structured editable interfaces; reserve implemented claims for the actual user-facing capability and link to that interface. Raw file I/O is not a structured editor. Use the same shared fitted paging controls as Blank, without clipped final rows or master-list scrolling. Audit the same claims/layouts across all plugins, not only Warband.

## Delivered implementation and evidence

PR #361 merged to master as bc6f97ef456b0a20b08358612c26eb400c97d2e7. All seven UI implementations, including the two FF7 editions that share an implementation, use the shared fitted Data Map. Explicit capability boundaries and per-dataset/subview links are documented in `codex/shared/data-map-coverage.md`. Preserved binary layers and inactive runtime controls do not claim structured editing.

CI run 34040197660 passed seven coverage tests on Windows/Linux and 24 rendered plugin/size cases including Warband. Fixtures exercise filtering, stable paging, available interface links and missing/source-only boundaries at 900x620, 1200x800 and 1600x1000. Narrow RDR2 and Warband screenshots were inspected. In-memory boot fixtures do not establish installed-game data coverage or deployment.

## Remaining acceptance

In the normal updated master checkout, follow Data Maps in `docs/warband-acceptance.md`: open each installed plugin's Map, filter/sort/page/resize and follow the available interface links. Warband skills must be Source only; missing files must not claim an editable interface. Notes may scroll in the detail pane, while list rows and the bottom pager stay fitted. Close source views without saving. Report plugin, source row, screenshot and incorrect destination/claim. The cross-plugin development audit is complete; actual installed-editor acceptance remains. No new design answer or code build is needed.
