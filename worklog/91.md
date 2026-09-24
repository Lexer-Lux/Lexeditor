# #91: Finish card creation, deletion and editing

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/91)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-08 existing-card save recovery

Live issue scope was read. Creating/deleting card types still requires engine, artwork, deck, reward and save support; this repair does not replace that scope with fixed-slot editing.

Existing-card saving previously wrote manifest and Hext separately, then attempted restoration in a loop that could stop on its first failure. The current save now takes snapshots before validation, stages both outputs and originals in one fixed `.cards-recovery` directory, checks for concurrent edits, and commits by atomic file replacement. Only installed outputs are restored. Failed restoration retains originals and a relative-path descriptor; later saves refuse to create more copies or use mismatched project state. Each source file is limited to 1 MiB before snapshotting; normalized output contains at most 660 scalar edits. Successful commit/rollback removes the temporary recovery set.

`tests/test_ff8_card_save_recovery.py`: eight tests pass. Covered normal merged edits, second-file failure, failed rollback plus repeated retry, external edits during staging/validation, first save rollback and oversized input. No user project or game file was changed. Existing-card gameplay acceptance and full new/deleted-card support remain open.

## 2026-09-22 misc-fixes evidence
Ran card suites on current tree: test_ff8_card_elements.py, test_ff8_card_save_recovery.py plus enemy-ai tests, 23 passed with 69 subtests. Existing-card edits (names, ranks, elements, selection power) hold in source. Card-type creation and deletion need engine, artwork (#300), deck, reward, and save support that does not exist here; existing-card edits still need in-game validation. Issue stays actionable.

## 2026-09-23 misc-fixes: flipped to waiting with concrete checklist

Per Lexer's rule (needs concrete Lexer-side work means waiting), posted the
exact game-session/decision checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
