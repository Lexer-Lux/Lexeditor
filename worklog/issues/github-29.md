# #29: Review Developer Mode and Restart controls

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/29)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.


## 2026-09-08 returned restart failure

User report: "restart without saving appears to not work. i press it and nothing happens."
The supplied screenshot shows the Blank unsaved-changes dialog with disabled actions.
Confirmed source defects: a false exit result left every action disabled without a
message; plugin restart awaited optional quote retrieval after replacing the service.
The shared dialog now shows pending/error state and restores actions after failure.
A missing restart URL throws a visible error. Navigation no longer awaits a quote.

`tests/restart_browser_check.py` drives the production Blank page and HostApi against
real disposable child services. Cancel keeps 102; Restart Without Saving closes the
old listener, starts a new service, navigates and restores 25. An unresolved quote
promise does not block it. False and missing responses leave Cancel enabled and show
the reason. Shared control tests and all 22 frontend syntax checks pass. The currently
open page must be closed and reopened to load the changed JavaScript. No user process
was terminated or user edits saved by the test. Issue returned to actionable after
the failed human test; the other Developer Mode/Home acceptance remains outstanding.

Source record: github-29/sources/20260908-restart-report/request.txt, with the original attachment and SHA-256 provenance. The explicit user archive rule supersedes the older no-archive text above.
Acceptance for this report: Restart Without Saving must replace the plugin service and discard its unsaved value; Cancel must preserve it; failed restarts must show an error and permit retry or cancellation. Automated checks pass; the user has not yet tested the reloaded page.

## 2026-09-08 global subagent follow-up

Live issue #29 still requires developer authorization, Home restart, and one-window
native acceptance. This batch fixes additional plugin restart and save defects.

- Clean restart failures show an error. Escape and outside clicks cannot dismiss
  a save/restart operation while it is in progress. A restart error after a good
  save is no longer reported as a save failure.
- Blank sample saves now use an atomic user-data file, with a 2 MB request limit
  and 100 sample limit. Restart changes the service port; browser localStorage
  could not retain the active saved sample across that change. The active sample
  and its title now restore. Save failure retains the dirty state. A failed read
  blocks saving so that unread sample data cannot be overwritten.
- Non-navigation project changes report success and refresh the current title.
- The real-service headless fixture creates Restart sample, verifies Cancel,
  save103/restart, edit104/discard/restart to103, and failed save105 without restart.
  It also tests clean failures, missing addresses, stalled optional quotes, and
  pending-dialog dismissal. All service data uses a cleaned temporary directory.
- Python checks: 19 passed, two explicit native-window skips. All11 browser suites
  passed across the full run and focused reruns after two fixture/flow repairs.
  Frontend syntax:22/22. Four new store tests cover atomic failure, corrupt input,
  invalid current sample, cross-origin writes, and storage size limits.

Files: ui/framework.js; games/blank/editor.html; games/blank/server.py;
tests/restart_browser_check.py; tests/test_blank_projects.py;
.github/scripts/ui_visual_acceptance.py.

No user window was restarted. No native-window acceptance is claimed. Keep the
issue actionable until its full remaining scope is prepared and confirmed.

Integration follow-up: the size-limit fixture now sets a 64-byte server limit and
sends a small over-limit body. This tests the same rejection branch without a
Windows large-upload/early-close socket race. It asserts HTTP400 and the storage
limit error. No exception broadening or production limit change. Focused store
suite4/4 and combined global suite19 passed,2 native skips.

## 2026-09-08 Home restart follow-up

Live #29 reread. Home now reports a missing restart confirmation, disables repeat
requests while a restart call is pending, and restores its control on failure.
The host checks its current dirty count, so a stale clean Home snapshot cannot
bypass unsaved changes. Repeated accepted requests destroy the window only once.
A failed window destroy restores restart/close flags and allows retry.

Three fake-window host tests pass. A new headless Home fixture verifies pending
request suppression, missing/error reply recovery, and owner-control visibility.
The existing Developer Mode verifier passes, including identity-only settings,
non-owner denial of packaged defaults, active-plugin replacement, and fake Home
restart. Frontend syntax22/22. Added Home fixture to the browser runner (12 suites).
No native window was opened or destroyed. Native one-window restart acceptance
remains unconfirmed. No issue status changed.

#86 was read live and still explicitly defers migration/comment cleanup. No
migration, archive, or deletion was done in this batch.
