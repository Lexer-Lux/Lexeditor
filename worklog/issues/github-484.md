# #484: Untangle the shared stylesheet

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/484)

## Requirements and decisions

Read the live issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-23 misc-fixes audit (machine-verifiable items)

Measured on the misc-fixes tree with tools/css_audit.py and tools/css_dead_code.py:

- Every plugin stylesheet at 0 real rules / 0 `!important` (was: ff8 666, rdr2 644, others up to 89). Enforced by tests/test_css_budget.py (green).
- framework.css: 0 duplicate selectors (was 464), 0 dead declarations (was 386), 1 `!important` (was 234).
- The single `!important` is `[hidden] { display:none !important; }`, deliberate and commented in ui/framework.css: as a layered rule it lost to unlayered display rules (Home restart/Lexer buttons showed while hidden). The budget test encodes the ceiling as 1 with that justification.
- Component-viewer counting is fixed: tools/generate_component_usage.py propagates through the framework call graph (shared_dependencies + propagate_usage); pager now reports 10 plugins, ui/component-usage.json is current, enforced by tests/test_component_usage_graph.py and tests/test_shared_ui_catalog.py.
- Style-snapshot baseline: ff7r-only --styles retry in progress (artifacts/snap-ff7r); earlier full baseline stalled at 456 files on an ff7r inner_text timeout.

Remaining, needs Lexer: accept the `[hidden]` ceiling of 1 (or authorize layering every component display rule so it can drop to 0), and confirm the snapshot baseline / style-diff-empty gate. Issue stays actionable.
