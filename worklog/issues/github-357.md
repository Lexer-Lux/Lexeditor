# #357: Stop binoculars crashing as they reach the player’s face

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/357)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.


## 2026-09-06 — RDR2 isolated batch / session rdr2-issue-batch

### Source finding and guarded candidate

The private runtime's put-away prompt scan dereferenced three getGlobalPtr
results without null checks. The candidate checks allocation, action and handle
slots independently before reading them. Existing registry coordinates and the
exact put-away action predicate are unchanged. No global prompt suppression or
invented animation/native is introduced.

A C++17 harness compiles and executes the actual production routine against
synthetic null/partial/invalid/unrelated/matching registries. Missing pointers
are safe and Study-like unrelated handles stay untouched. The dispatcher and
binocular task/camera/forced-aim boundaries now have specific crash stages,
using existing trace retention rather than deleting logs.

This is a demonstrated null-dereference hazard, NOT a proven explanation of the
reported crash. The environment lacks the Windows game and checked-in
ScriptHook SDK; these unit checks are not an ASI build or game test. Keep #357
actionable pending compiled delivery and the real exception/entry reproduction.
