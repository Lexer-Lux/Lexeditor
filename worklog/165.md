# #165: Recover lost unique weapons through the normal locker list

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/165)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #66 worklog](github-165/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-66.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes disposition
Recover action workaround installed; ordinary locker-list entries need the native melee and throwable filter solved safely. Verify the filter approach before another acceptance request for the workaround. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side filter/asset/
prototype still owed), so flipping to waiting would be a fake checklist.
Left actionable until a real session can be written.

## 2026-09-23 agent review (per-game-rdr2): no new agent-side slice, stays actionable

Re-read the live issue plus comments. The named Recover action workaround
is installed but ordinary locker-list entries are still owed. Exact needs:
a safe solution to the native melee/throwable filter, then game
verification that lost unique hatchets/tomahawks return through the camp
locker unequipped and without duplication. No code written; recording the
needs here instead of re-requesting acceptance of the workaround.

## 2026-09-23 agent slice (per-game-rdr2): checkable recovery contract

games/rdr2/locker_recovery.py pins the acceptance boundary as data
(evidenced Viking Hatchet plus unique hatchet/tomahawk classes) and
validate_recovery_plan(), which requires the ordinary locker list route,
unequipped return, a duplication check, and ownership of the unresolved
melee/throwable filter. Covered by tests/test_rdr2_locker_recovery.py
(9 hermetic tests). No gameplay claim: the filter solution and the game
session are still owed.

## 2026-09-23 agent slice (impl/rdr2-wave2): filter acceptance criteria

plugins/rdr2/locker_recovery.py gains FILTER_ACCEPTANCE_CRITERIA
(ordinary-list visibility, non-unique exclusion, unequipped return, no
duplication on revisits) plus validate_locker_filter(), which rejects
any plan that assumes the native filter solved. Covered by 6 new tests
in tests/test_rdr2_locker_recovery.py (15 total, green). No gameplay
claim: the filter solution and the game session are still owed.

