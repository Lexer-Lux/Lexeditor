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

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (native research/design still
owed), so flipping to waiting would be a fake checklist. Left actionable
until a real session can be written.

## 2026-09-23 agent review (per-game-rdr2): no new agent-side slice, stays actionable

Re-read the live issue plus comments. No Honor reference exists outside
honor_actions.cpp event amounts and no shop price-modifier mechanism
exists anywhere in the tree, so the independent shop-modifier correction
is still unbuilt. Exact needs: native shop-script research finding the
per-shop Honor price hook with the game, then a purchase-comparison
session. No code written; recording the needs here instead of inventing
a hook.

## 2026-09-23 agent slice (per-game-rdr2): comparison contract

games/rdr2/fence_price_check.py pins the valid purchase comparison as
code plus validate_price_check(), which requires low-Honor and
high-Honor legs at one fence for one item with readable prices, rejects
cross-shop/cross-item comparisons and normal-store substitutions, and
requires ownership of the unbuilt shop-modifier correction. Covered by
tests/test_rdr2_fence_price_check.py (8 hermetic tests). No gameplay
claim: the correction and the comparison session are still owed.

