# #206: Prepare complete tests for the five bait changes

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/206)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes finding: table needs deployed data
Searched native modules, plugin JS/PY data, codex topics, and this handoff for the five bait values: no bait pricing, outputs, recipe costs, or stations exist in the repo (bait appears only as editor carry-capacity help and purchase-container wiring). The exact expected results live in the deployed shop/catalog data, so the test table needs game-machine extraction first. The handoff conversation mirrors the issue text only. Issue stays actionable.

## 2026-09-22 misc-fixes: table prepared headlessly, no game machine needed
The earlier note was wrong that extraction needs the game machine:
`get_catalog('mine')` on the editable dataset returns all five bait records
with buy/sell, shop listings, carry, and craft costs. Prepared table posted
to the issue (buy 5/5/5/10/10; craft bread 1 roll->6 or 1 chunk->3, cheese
1 wedge->3, corn 1 corn->3; sell 2/2/2/5/100; ST_BAIT x1 all, ST_GENERAL
extras for tin/can; satchel cap 3 each). Open flag: worm can sells for 100
against a 10 buy price, a possible infinite-money loop if honored in game.
Remaining scope is the in-game purchase/consumption test. Issue stays
actionable. (Note: one truncated comment fragment was posted by mistake and
immediately superseded by the full table; comments cannot be deleted.)

## 2026-09-23 master: flipped to waiting with concrete checklist

Posted the exact game-session checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
