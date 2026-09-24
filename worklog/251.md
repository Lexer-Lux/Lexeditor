# #251: Restore climbing entry before testing animation stop

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/251)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #159 worklog](github-251/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-159.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes disposition
Sequenced behind #193, which now carries a delivered entry/surface candidate with a live checklist (vertical wall grab, cluttered/angled geometry, safe release, normal jumps unchanged). Re-ran tools/verify_rdr2_climb_transitions.py on current tree: PASS production, four regressions rejected (fall-called-grounded, fall-velocity-cleared, cooldown-bypassed, timeout-called-grounded).
Human test, needs built ASI on a game machine after #193 entry passes: climb, release movement, confirm the cycle stops into idle; releasing Sprint while still moving must keep climbing. Report stop behavior per input. Issue stays actionable.

## 2026-09-23 master: flipped to waiting with concrete checklist

Posted the exact game-session checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
