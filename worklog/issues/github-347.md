# #347: Reduce RDR2 editor startup time

[Full request and discussion archive](github-347/conversation.md)

## Requirements and decisions

Recover the complete scope from the linked verbatim sources before implementation or status changes. The short GitHub summary is not the full specification. Do not infer that missing chat text was never supplied.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. This archive import makes no build, deployment or gameplay-success claim.

## Next agent work

Read the source records and preserve the latest explicit human corrections. Update this handoff, not a shared global Worklog.txt.


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
