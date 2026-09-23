# #167: Build a viable prone weapon-animation prototype

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/167)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #68 worklog](github-167/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-68.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes disposition
Prone weapon animation needs compatible clips or authored upper-body poses; reusing unchanged clips already failed its test. Asset creation workflow comes first, with a specified test after. No code written. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side filter/asset/
prototype still owed), so flipping to waiting would be a fake checklist.
Left actionable until a real session can be written.

## 2026-09-23 agent review (per-game-rdr2): no new agent-side slice, stays actionable

Re-read the live issue plus comments. Reusing unchanged clips failed its
test, so prone needs compatible clips or authored upper-body poses. Exact
needs: RDR2-compatible authored animation/export pipeline plus visual
animation work (draw/holster/idle/aim/fire/reload sets, reticle-driven
aim poses, recoil/reload events, binocular handling, upper-body masks,
contacts, zero root motion), then Lexer visual QA. No code written here.

## 2026-09-23 agent slice (per-game-rdr2): honest settings help

settings_schema.json gains the missing Prone|GroundedAimMode help: test
mode runs the authored grounded aim loop so the wheel opens prone, while
reload stays blocked, longarms/binoculars are unsupported, and shots
need in-game reticle validation. Guarded by
tests/test_rdr2_settings_help.py. No gameplay claim: the authored
animation pipeline and visual QA are still owed.

