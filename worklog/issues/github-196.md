# #196: Prepare the shared ammunition-cap test

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/196)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes disposition
Shared caps are implemented (#70 in combat_inventory.cpp: one combined limit per family, ini-configured, overflow trimmed from the last-picked variant; 0 keeps vanilla). The requested Revolver=100 mixed-ammo test still needs the #194 ammo-count display delivery plus reliable in-game before/after totals, which need the game. No code change. Issue stays actionable.

## 2026-09-23 master: flipped to waiting with concrete checklist

Posted the exact game-session checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
