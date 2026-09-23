# #204: Deliver the corrected fence Honor pricing

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/204)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes finding: blocked, no hook in tree

Searched the whole RDR2 plugin for fence Honor pricing: no Honor reference outside honor_actions.cpp (event amounts, #62), the settings schema, and script.cpp wiring; no price logic outside world_economy.cpp bounty payment and merchant-buy satchel gating; no shop price-modifier mechanism anywhere (modifier matches only a radar blip flag).
The independent shop-modifier correction named in the issue body is not in this tree, and the issue has zero comments pointing at it. Finding the per-shop Honor price hook is native shop-script research needing the game, not a misc fix.
Recorded the negative evidence here instead of inventing a hook. Issue stays actionable.
