# #238: Grey out items blocked by insufficient cores

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/238)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #146 worklog](github-238/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-146.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes diagnostic
Read core_cost_guard.cpp fully. The guard already disables via INVENTORY_DISABLE_ITEM with satchel-predicate readback, plus quick-use disable and interaction reject. Use-blocking works; the radial grey does not, so the radial likely reads a different availability source than the satchel predicate confirms.
Human test, needs built ASI on a game machine: drain one core, use a negative-effect item, then check GameplayTweaks.log for the availability block line. If confirmed=1 yet the radial entry is not grey, the radial source needs native research. If writes abandoned appears, the setter does not own that item. Report the exact log lines with which surface (radial vs satchel) greys. Issue stays actionable.

## 2026-09-22 production evidence from Sept 6 log
Mined the installed GameplayTweaks.log: availability blocks with confirmed=1 occurred live (moonshine, cigarette box), zero abandonments. The disable path provably sticks in game. Remaining question is only whether the radial renders the disabled state; check the radial against those log timestamps. Issue stays actionable.
