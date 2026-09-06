# Issue #86 — deferred knowledge consolidation

## Latest scheduling instruction — verbatim

Source: Lexer, current ChatGPT conversation, September 6, 2026. Exact message time and message ID are not available.

> Never mind then. We should do that later. Add it as a global issue -- to merge all the codices and worklogs and format them as I specified.

Implementation is deferred at Lexer's request. Recording this task does not authorize resuming migration, merging branches, deleting comments, or restarting cleanup jobs now. Keep `global`, `documentation`, and `actionable`; this is deferred agent work, not `waiting` on Lexer.

The complete earlier user request is preserved in [the original source record](sources/chat-2026-09-06-preservation-request.json). That wording remains authoritative; the scope below is an agent-organized acceptance specification, not another purported verbatim quotation.

## Complete required scope

1. Inventory and reconcile all relevant codices and worklogs across Lexeditor, every Lexer's game-mod repository, legacy files and available parallel branches. Preserve the originals and their source repository/path/commit. Do not mistake an export, empty template, README or generic handoff for a completed import. Identify inaccessible or uncommitted local notes honestly; never silently omit them or claim GitHub contains them.
2. Centralize settled knowledge in Lexeditor under `codex/<game>/`, with a separate codex for each game and topic-owned files. Shared editor knowledge belongs in `codex/shared/`. Confirmed mechanics, schemas, source paths and demonstrated engine limits belong here, in present tense. Correct outdated facts in the owning topic; retain contradictory historical evidence separately. Do not treat an imported failed attempt as a proven engine limit. Provide an index and automatically scaffold/validate codex coverage for new plugins.
3. Maintain one active internal worklog per issue at `worklog/issues/github-<number>.md`, with the complete requirements, decisions, implementation state, remaining work, attempts, test results and deployment evidence. Preserve immutable original request/comment records alongside it in `worklog/issues/github-<number>/sources/`. Map transferred issue identities explicitly instead of assuming old and new numbers match. Legacy `Worklog.txt`/`CODEX.txt` may become generated indexes or forwarding pointers, not competing shared hand-edited trackers.
4. Preserve Lexer's full original wording, examples, numbers, exceptions, rejected alternatives, attachments and subsequent corrections before shortening any human-facing text. Recover previously omitted requirements from archived bodies/comments, legacy stores and available original chat/file sources. Never equate a short GitHub body with an incomplete user explanation. Ask again only about a genuinely unresolved point after retrieval; recovery work remains actionable.
5. Keep GitHub titles and bodies brief: requested outcome, true current status and only what a human needs to act. `waiting` means a concrete action/decision from Lexer and ends in its unchecked checklist. `untested` means an available test candidate with setup, steps, expected result and what to report in a final unchecked checklist. Unfinished implementation, delivery, test preparation and deferred agent work remain `actionable`. Preserve game and priority labels independently.
6. Migrate all issue discussion, including human and agent comments, into verified durable internal records before deleting the visible comments. Preserve authors, IDs, URLs, timestamps, exact text and necessary attachments. Commit and read back the archive first; expiring workflow artifacts are not sufficient. Re-read each comment immediately before deletion and skip changed/new or incompletely preserved records. Do not delete issues or unrelated PR reviews. Review and repair the existing archive tooling rather than assuming its earlier runs completed.
7. Use per-issue ownership and distinct contributor/session records to avoid concurrent edits to a global worklog. After the active parallel branches are merged, perform an incremental reconciliation for newly added or changed codex/worklog material. Track source hashes and provenance, preserve newer central work, resolve semantic conflicts and verify source coverage before retiring any old store. Leave forwarding pointers. Do not interfere with active workers or automatically merge their game code as part of documentation work.
8. Review private-source material before publishing into public Lexeditor. Preserve the requested project documentation without uploading credentials, private binaries, proprietary game dumps or unrelated personal data. Retire only superseded active handoffs; never destroy original request/decision evidence on completion.

## Acceptance boundary

Completion requires an auditable source-to-destination inventory, populated per-game codices, substantive per-issue worklogs, exact preserved requirements and discussion, verified safe comment cleanup, and a documented incremental catch-up procedure. Missing sources and unresolved conflicts must remain explicit. Passing a script or creating infrastructure alone does not complete this issue.

## Previous visible issue body — preserved verbatim before expansion

Source: https://github.com/Lexer-Lux/Lexeditor/issues/86; fetched in this turn. Title: Keep game research in Lexeditor, not mod repositories. Reported update time: 2026-09-06T12:38:31Z. No comments were present in the fetched discussion.

```text
Each game plugin needs its own technical codex in Lexeditor. New plugins should receive one automatically, with a check for missing documentation. Mod repositories keep distributable mod files, not duplicated research or attempt logs.

**Status: Migration and validation remain unfinished.** No action from you is needed.
```

## Resume note

The earlier issue-comment archive/cleanup run 34037390327 is now terminal with conclusion `failure`. This note makes no claim about the exact number of archived or deleted comments. When this deferred task is resumed, inspect its committed records and verified results before retrying anything; never repeat deletions or imports blindly.
