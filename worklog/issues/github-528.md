# #528 — Repair RDR1 unit contracts after string-table backend removal

Status: fixed on `per-game-misc` (this branch). `tools/verify_rdr_editing.py`: 29/29 green.

## Root cause (corrected)

The issue text blames "#487 refactor" for removing string-table routing from
`games/rdr/server.py`. Archaeology shows it was the #487 *merge* (`a13f3e58`):
the second parent (`90f5c066`) carried the full backend
(`STRING_TABLE_SOURCES`, `string_tables_index`, `string_table_payload`,
`strings_payload`, `save_string_table`, `rbf_scalars_payload`,
`save_rbf_scalars`, plus 6 HTTP routes), layered on `string_tables.py` /
`rbf.py` — and the merge result kept master's side of `server.py`, dropping
489 lines. `git diff 90f5c066 HEAD -- games/rdr/{string_tables.py,rbf.py}
tools/rdr_test_support.py tools/verify_rdr_editing.py` is empty, so the format
modules, fixtures and contracts were intact; only the server backend was lost.
Side effect beyond tests: the editor's Strings and Tuning tabs call
`/api/string-tables` and `/api/rbf-scalars`, which had no route (dead tabs).

## Fix (this branch, `games/rdr/server.py` only)

Restored the dropped backend, reusing the current `string_tables.py` /
`rbf.py` modules (no logic duplication):

- `from . import (..., rbf, ..., string_tables)` and `STRING_TABLE_SOURCES`.
- `_rbf_paths`, `_rbf_resource_rows`, `rbf_scalars_payload`, `save_rbf_scalars`.
- `_string_table_supported`, `_string_table_paths`, `_string_table_metadata`,
  `string_tables_index`, `string_table_payload`, `strings_payload`,
  `save_string_table`.
- `is_editable` again excludes `RBF0` binaries from the text editor.
- `_provisional_data_map_rows` again indexes tuning/content string tables,
  RBF scalars and the loot-script row with `game/<archive>:/<path>` filenames;
  inventory/gringo rows use the same prefixed form; `_normalize_data_map_rows`
  prefers capability controls.
- Routes restored: `GET /api/string-tables`, `/api/string-table`,
  `/api/strings`, `/api/rbf-scalars`; `POST /api/string-table/save`,
  `/api/rbf/save`; `string-tables` + `rbf0-scalars` capabilities.

Deliberately NOT restored (branch-only cosmetics, unrelated to the contracts):
old-base `PluginRequestHandler` import fallback, `log_message` silencer,
Windows `creationflags` on the loot-tool subprocess, dashboard "content"
relabels, `hasattr(send_page_module)` guard (master's shared
`send_page_module` already serves `strings.js`/`rbf.js`).

## Verification (worktree `C:\Lexeditor-per-game-misc`, base `origin/master`)

- `python tools/verify_rdr_editing.py` — 29 tests OK (was 29 errors).
- `python -m unittest tests.test_rdr_string_tables tests.test_rdr_rbf` — OK.
- `verify_rdr_items_split_issue_19.py`, `verify_rdr_data_map_audit.py`,
  `verify_rdr_mod_compatibility.py` — exit 0.
- `verify_rdr_cache_reuse_71.py` — fails identically with and without this
  change (needs real game archives/tool; pre-existing environment failure).
- Browser legs (`verify_rdr_editing_browser.py`, `tests/rdr_browser_check.py`)
  not run here (need Playwright/Chromium); left for CI.
- Follow-up `fcb52f73`: loot row also gates on `LOOT_FILE.is_file()`;
  `test_data_map_coverage.py` 8/8 and `verify_rdr_editing.py` 29/29 green
  in this worktree after the change.

## CI on PR 541 after `fcb52f73` (not caused by this branch)

- `editor` fails in `tests/rdr_browser_check.py:201`: label-lane ratio
  0.189 > 0.16 at 900px on the items Amount field. This branch does not
  touch that test, `ui/framework.*`, or `games/rdr/editor.*`
  (`git diff origin/master...HEAD` on those paths is empty); the lane
  fitter (12f3575c) is already in master. Pre-existing/environmental.
- `Stardew rendered UI acceptance` fails on a different game; out of scope.
- Master itself is red in the same lanes (Shared UI contract, FF9
  verification failed on the #540 merge push), so these are not PR 541
  regressions. Left for the owning lane work, not chased here.

## Remaining (needs Lexer / game)

- Strings/Tuning tab round trips against a real RDR1 install (prepared-data
  extraction + one reversible edit each) were never demonstrated; unit
  contracts are synthetic-fixture only.
