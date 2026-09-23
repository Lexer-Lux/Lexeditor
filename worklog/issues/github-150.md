# #150: Clarify enemy stats and the walking-target accuracy problem

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/150)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes disposition
Mobs editor exposes WeaponAccuracy and offset modifiers per faction with pedaccuracy.meta finishing; no universal per-model record exists and none is pretended. The walking-target misses match a directional penalty blind to gait. Controlled test, needs the game: same shooter and target at stationary, walk, and sprint, recording hit rate per gait before any rebalance values are proposed. Issue stays actionable.

## 2026-09-23 master: flipped to waiting with concrete checklist

Posted the exact game-session checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
