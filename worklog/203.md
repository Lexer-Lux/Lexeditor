# #203: Prepare a controlled Viking Hatchet cash test

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/203)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes: payout logging plus open 4x question
Added per-victim viking log lines (rolled, bonus, added) to updateVikingVictims with zero behavior change, so the controlled test can measure instead of guess. Open question flagged in code: the top-up is 4x the rolled loot on top of it (5x total), while the spec says 4x. Do not edit the multiplier until measured.
Controlled test, needs built ASI on a game machine: kill ordinary victims with the Viking Hatchet outside missions, loot each, collect viking log lines over several victims. bonus divided by rolled must read exactly 4 every time; item loot and mission payouts must stay untouched (both already guarded in code). Report the log lines; the 4x-total verdict then decides one line change. Issue stays actionable.

## 2026-09-23 master: flipped to waiting with concrete checklist

Posted the exact game-session checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
