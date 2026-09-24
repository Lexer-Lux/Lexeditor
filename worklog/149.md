# #149: Finish wanted-system research after the trace crash repair

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/149)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #50 worklog](github-149/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-50.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes disposition
Diagnostic crash repaired; the overhaul itself remains research: duration/state experiment plus a concrete persistent-zone prototype with re-entry consequences, all needing the game. Drawn circles alone do not prove law behavior. No repo change available. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side prototype/experiment
still owed), so flipping to waiting would be a fake checklist. Left
actionable until a real session can be written.

## 2026-09-23 master: analysis slice delivered, flipped to waiting

Built tools/analyze_wanted_trace.py from the trace module's specified line
format (modules/wanted_system.cpp): folds samples into state-duration rows
with the parole columns plus F8 dark-red windows. Covered by
tests/test_analyze_wanted_trace.py (5 hermetic tests, green). The game half
(crime/escape run with F8 marks plus the log) and the persistent-zone
prototype that follows from its results are Lexer-side. Flipped to waiting
with the run checklist.
