# #161: Add real per-action honor amounts

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/161)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #62 worklog](github-161/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-62.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes finding
honor_actions.cpp (80 lines) holds event bit controls plus shared tier remapping from CSV. No per-action amount path exists: the engine applies tier amounts after the event fires, and intercepting one event before its identity is lost is unproven. That interception proof is native research needing the game. No invented hook added. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side fixes/research still
owed), so flipping to waiting would be a fake checklist. Left actionable
until a real session can be written.

## 2026-09-23 agent slice (per-game-rdr2): shared-tier regression guards

tests/test_rdr2_honor_action_amounts.py locks the recorded finding into
games/rdr2/honor_actions.py: event edits cannot carry an independent
amount, tier amounts stay editable, the scope note states shared tiers
(not independent per-action values), and the 21-event/19-tier tables keep
their shape. (4 hermetic tests.) No gameplay claim: intercepting one
event before its identity is lost still needs native research with the
game.

