# #180: Remove redundant cigarette-card glints

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/180)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #83 worklog](github-180/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-83.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-06 — source retirement verified and permanently guarded

The custom cigarette-card glint implementation is already absent from the current runtime source. The existing regression `verify_cigarette_card_glint_removal_issue_83.py` explicitly checks that the card glint remains removed while unrelated spent-casing glints remain present. It passed again during the deterministic cleanup batch and is retained in permanent runtime CI.

No replacement card-glint code was added. This issue requested removal rather than another visual iteration, so there is no unchanged old gameplay test to repeat. Runtime cleanup product commit `b33e540ac6392bab73c174248f1eb8d8402cc76f`; permanent-CI follow-up `0fbc622a2010658e08776be2e77b4214dcf2cedc`. Merge/delivery remains separate from source verification.
