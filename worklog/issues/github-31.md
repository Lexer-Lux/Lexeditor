# #31: Finish the Formulae Rework

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/31)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes status
Healing and accuracy runtimes stand (tests green). Melee, magic-damage, and status-infliction patches are still missing: each needs hand-written x86 against its routine, which cannot be validated without the game, so no blind machine code was written. Mug prerequisite done on this branch (explicit Difficulty contract plus tests, see github-408.md); the Mug comparison patch itself remains. Formulae page scroll report still needs a rendered check. Issue stays actionable.
