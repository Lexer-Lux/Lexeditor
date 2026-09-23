# #291: Prepare the installed saddle-lantern test

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/291)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes finding
No saddle or horse-lantern code exists anywhere in the runtime tree (only belt_lantern.cpp matches lantern). The reported-installed implementation is not in this tree, and no shop or item route names it. The test needs the exact purchase and equip path plus light-control fixes first. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (purchase/equip path plus
light-control fixes still owed), so flipping to waiting would be a fake
checklist. Left actionable until a real session can be written.
