# #181: Make binocular transition speed actually change

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/181)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #84 worklog](github-181/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-84.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.


## 2026-09-06 — RDR2 isolated batch / session rdr2-issue-batch

### Current decision and paired runtime candidate

The latest explicit request permits removing the ineffective speed control.
The public schema hides legacy TransitionAnimRate/TransitionAnimLayer entries
so stale external INIs cannot present them as useful settings. The paired
private branch fix/lexeditor-rdr2-issue-batch removes the runtime observer,
animation-speed setters, config/default and generated menu row. The native
satchel swap, draw/stow timing, latch and camera-readiness paths remain intact.

The runtime schema is regenerated against that repository's own matching
schema, not overwritten with a newer public schema that would retune unrelated
menu rows. The obsolete legacy probe verifier now asserts the explicit
retirement acceptance instead of requiring the rejected control.

Source/unit checks pass. No ASI build/install or visible animation-speed
improvement is claimed. The crash in #357 still blocks an in-game comparison.
