# #347: Reduce RDR2 editor startup time

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/347)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.


## 2026-09-06 — RDR2 isolated batch / session rdr2-issue-batch

### Implemented

Localization aliases and crafting validation reuse the mtime/path-validated XML
cache. Provenance keeps one entry per dataset instead of reference loading
evicting the editable entry. Its key includes active catalog paths and localized
name sources. Independent bootstrap requests start together; required results
are published together. The loading screen is dismissed only after final async
rendering with booting=false. A generation counter prevents stale dataset loads
from replacing the currently selected dataset.

### Agent checks

22 hermetic Python regressions plus four executed Node cases pass. The JavaScript
cases use production functions and controlled promises for API success, required
failure, optional failure, final rendering and out-of-order dataset completion.
Full inline JavaScript parses successfully. Matched cold-process local checks of
localization, crafting and catalog (including JSON serialization/hash work),
three runs each: median 7.460s before, 4.145s after, 44.4% lower.
All three API response SHA-256s match before/after in all six runs, including
5,096 catalog items. This is a local backend benchmark, not a promised Windows
end-to-end startup time. Direct browser navigation was blocked by this
execution environment's administrator policy; no visual acceptance is claimed.

### Remaining

Review/merge and validate the real hosted editor's loading transition. Keep this
issue actionable until a delivered candidate is confirmed under project rules.
