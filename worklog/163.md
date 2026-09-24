# #163: Remove masks reassigned to challenge rewards

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/163)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #64 worklog](github-163/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-64.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes diagnostic
Read world_collectible_masks.cpp fully: Cat Skull Mask is listed with model and authored position, suppression is careful (hide plus freeze plus 50 m drop, never delete), and the tick is wired in script.cpp. The module logs every attempt with before and after coords plus an ok flag.
Diagnostic test, needs built ASI on a game machine: visit the Cat pickup, then read the world-masks log. No suppress line means the prop never sits within 3 m of the authored point while the player is near (wrong position or a second pickup). An ok equals 0 line means the setters did not stick. Report the log lines with the observed pickup position. Issue stays actionable.

## 2026-09-22 production evidence from Sept 6 log
Mined the installed GameplayTweaks.log: world-masks stayed idle the whole session (nearby=0, scans=0, suppressions=0). The sweep never saw any authored point, so the Cat pickup the player found is not within 150 m of the listed position or is a different spawned instance. The fix is locating the real pickup position, not stronger suppression. Next: record the observed pickup coordinates from the next visit and compare against the authored point. Issue stays actionable.

## 2026-09-23 master: flipped to waiting with concrete checklist

Posted the exact game-session checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
