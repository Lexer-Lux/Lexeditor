# #357: Stop binoculars crashing as they reach the player’s face

[Full request and discussion archive](github-357/conversation.md)

## Requirements and decisions

Recover the complete scope from the linked verbatim sources before implementation or status changes. The short GitHub summary is not the full specification. Do not infer that missing chat text was never supplied.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. This archive import makes no build, deployment or gameplay-success claim.

## Next agent work

Read the source records and preserve the latest explicit human corrections. Update this handoff, not a shared global Worklog.txt.


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
