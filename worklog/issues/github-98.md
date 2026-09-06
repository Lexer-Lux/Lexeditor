# #98 — Coverage and paging

Completed the cross-plugin audit in `codex/shared/data-map-coverage.md`. All seven
UI implementations (including both FF7 editions) use the shared Data Map component,
which composes the fitted Table + Detail view instead of fixed 100-row slicing.
Warband no longer duplicates its map shell. Claims distinguish structured partial
support, read-only interfaces, source-only access and unavailable files. FF7 links
individual KERNEL categories; FF9 links the exact CSV dataset; FF8 links the actual
subview. RDR generated metadata is reconciled against actual supported sources.
RDR2 preservation-only component layers and inactive projectile runtime controls
are no longer called editable.

Local coverage tests passed. Actual plugin HTML/CSS/map adapters were rendered
with in-memory fixtures at 900x620, 1200x800 and 1600x1000; notes scroll only in the
detail pane, the master has complete rows, and there is one shared pager. Added
pagination stability and source/read-only link checks. No installed game files
are touched by these tests. CI run 34037391185 passed the 24 browser cases and
Linux tests; its Windows failure was a test-only short/long path comparison,
corrected in db829de. Final integration uses PR #361 and its latest checks.

## Sources and acceptance

The pre-completion public body is preserved verbatim in
`github-98/sources/2026-09-06-before-completion.json`. Earlier full requests and
comments remain in `worklog/legacy/issue-status-audit-2026-09-06/`; the continuation
request is in `github-97/sources/2026-09-06-chat-request.txt`.

The shared component, per-plugin adapters and coverage tests address the requested
cross-plugin scope, not just Warband. Prepared installed-editor checks are in
`docs/warband-acceptance.md`; `tools/Warband-checks.cmd` runs all disposable Python
fixtures without editing game assets, then opens Warband. Final merge evidence
is PR #361. Neither this handoff nor CI claims installation on Lexer's PC.
