# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356169067 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/98

Created: 2026-09-05T06:31:30Z; updated: 2026-09-05T06:31:30Z

Exact metadata: [source record](sources/issue-5356169067-0f085b2e57a20c1ecc6f9c0dc373f2879273fc471b78116eb6724834ac20664d.json).

Warband Data Map labels skills and most source files implemented/integrated despite no dedicated view/edit interface. Its vertical scrollbar also conflicts with fitted pagination seen in Blank. Lexer reports similar gaps across several plugins.

Confirmed source findings:
- Warband data_map_rows marks every catalog area except Generated output integrated. This means raw Python source editing, not a structured editor. module_skills.py has only that source-editor route.
- Warband calls shared dataMap with pageSize=100. That helper uses fixed slicing and does not use fitted paging. Blank uses pagedListDetail with fit:true.

Deferred repair scope: distinguish source-only, view-only, and structured editable coverage; reserve implemented status for the claimed user-facing capability; link each claim to its actual interface. Bring Data Map pagination and affected plugin layouts onto the same shared controls as Blank, with rendered checks at different window sizes. Audit other plugins for the same misleading claims and alternate control paths. Do not infer data editors exist from file read/write support.

Recorded for later; no repair work authorized in this deferred item yet.

## issue 5356169067 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/98

Created: 2026-09-05T06:31:30Z; updated: 2026-09-06T13:02:32Z

Exact metadata: [source record](sources/issue-5356169067-3fa3f8297ffcaa35cec51afafe0faef2e4d5da5350adb2e84ff5d13f0c5e97cb.json).

Warband repair is in PR #361, not yet merged: structured editing, read-only views, source-only access and missing files have distinct labels and links. Data Map uses the shared fitted pager; rendered checks pass at three window sizes.

**Still needs development:** audit and repair the same claims/layouts in the other plugins. They were deliberately left untouched during parallel game work. The full cross-plugin issue remains open; no design decision is needed from you.

## issue 5356169067 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/98

Created: 2026-09-05T06:31:30Z; updated: 2026-09-06T13:02:32Z

Exact metadata: [source record](sources/issue-5356169067-e91b241382f536892fa0d399492489c218fd5478ab0e88e22fe43635e01d2009.json).

Warband repair is in PR #361, not yet merged: structured editing, read-only views, source-only access and missing files have distinct labels and links. Data Map uses the shared fitted pager; rendered checks pass at three window sizes.

**Still needs development:** audit and repair the same claims/layouts in the other plugins. They were deliberately left untouched during parallel game work. The full cross-plugin issue remains open; no design decision is needed from you.
