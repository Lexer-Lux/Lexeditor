# #144: Prepare a valid vanilla casing-ejection comparison

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/144)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #45 worklog](github-144/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-45.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.


## 2026-09-06 — RDR2 isolated batch / session rdr2-issue-batch

### Implemented

The restore/blank operation covers the base weapon file plus all six authored
YMT overrides. Status aggregates all seven files and reports missing references
and records. Active install.xml replacement paths are respected, and all eleven
stack resources must be present. All trees are validated before writing,
including projectile-flag preservation in patch files. Caught late write/install
failures restore prior file bytes, mappings and cached roots. Existing .bak
files are retained. Power-loss recovery is not claimed.

### Agent checks

Synthetic regressions cover restore/reblank idempotence, mapped paths,
missing references/records/components, invalid flags, wrong input types,
traversal rejection and late save/install rollback. An isolated copy of the
actual project stack restored exactly 61 fields across seven files, then
reblanked exactly 61. Every other parsed XML field/attribute/tail was unchanged.
Original project/game files were not edited by that integration check.

### Remaining scope (not closed by this repair)

This repairs the invalid vanilla comparison setup; it does not calibrate custom
casing trajectories. Actual first/third-person, weapon-family and both-hands
visual/momentum comparisons and subsequent custom tuning remain actionable.
