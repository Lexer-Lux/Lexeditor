# #111: Improve the replacement inventory icons

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/111)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #11 worklog](github-111/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-11.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes disposition
Icons appear but look poor: artwork-quality task, not missing images. Replacement previews come before any approval ask, then a pickup and acquisition-card check with the art toolchain. Unapproved YTD must not ship. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side previews/prototype
still owed), so flipping to waiting would be a fake checklist. Left
actionable until a real session can be written.

## 2026-09-23 agent slice (per-game-rdr2): icon-input presence guards

tests/test_rdr2_issue111_icon_sources.py locks the art-toolchain inputs in
games/rdr2/assets/item-icons: source PNGs for pistol, revolver, repeater,
rifle, shotgun, varmint, and 225 casings, 225 AP ammunition, and empty
bottles, plus the two review previews. (2 hermetic tests, presence only.)
No art claim: quality and Lexer approval still need the art toolchain and
a game check (pickup plus acquisition card). Hull artwork has no
checked-in source yet and stays a Lexer art question.

