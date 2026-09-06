# #131: Fix incorrect per-drink alcohol strengths

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/131)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #31 worklog](github-131/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-31.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.


## 2026-09-06 — RDR2 isolated batch / session rdr2-issue-batch

### Implemented

Save only explicit per-drink edits, merging with the latest persisted overrides
instead of resending a stale browser's entire effective table. Re-read persisted
values after saving. Reject booleans, non-finite and out-of-range values; do not
silently clamp bad input to zero/one. Preserve unknown existing rows by refusing
the save rather than deleting them. Preserve float round-trip precision rather
than six-significant-digit formatting. Missing baseline data produces explicit
unavailability, and an unknown drink has no fabricated zero-valued editor.

### Agent checks and limits

Regression cases cover distinct values, intentional strength 1, sparse edits,
concurrent unrelated changes, baseline resets, precision, invalid inputs and
missing/duplicate data. The current private source data already contains 14
distinctly authored drink records; the deliberate Moonshine=1 override is kept.
The reported all-ones UI state was not reproduced against this source revision.
These repairs prevent confirmed save/data-loss defects; they are not proof the
original screenshot's root cause is fixed. Compare the delivered editor's
rendered rows with the selected runtime CSV before closing #131.

## 2026-09-06 — Header Save follow-through

[Reproduced missing alcohol-only Save dispatch, repair and executed UI checks](github-131/sessions/20260906-header-save.md). The earlier handler-level tests did not cover this global button path; the new checks do. Original real-project display acceptance remains open.
