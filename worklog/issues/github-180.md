# #180: Remove redundant cigarette-card glints

[Full request and discussion archive](github-180/conversation.md)

## Requirements and decisions

Recover the complete scope from the linked verbatim sources before implementation or status changes. The short GitHub summary is not the full specification. Do not infer that missing chat text was never supplied.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. This archive import makes no build, deployment or gameplay-success claim.

## Next agent work

Read the source records and preserve the latest explicit human corrections. Update this handoff, not a shared global Worklog.txt.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #83 worklog](github-180/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-83.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-06 — source retirement verified and permanently guarded

The custom cigarette-card glint implementation is already absent from the current runtime source. The existing regression `verify_cigarette_card_glint_removal_issue_83.py` explicitly checks that the card glint remains removed while unrelated spent-casing glints remain present. It passed again during the deterministic cleanup batch and is retained in permanent runtime CI.

No replacement card-glint code was added. This issue requested removal rather than another visual iteration, so there is no unchanged old gameplay test to repeat. Runtime cleanup product commit `b33e540ac6392bab73c174248f1eb8d8402cc76f`; permanent-CI follow-up `0fbc622a2010658e08776be2e77b4214dcf2cedc`. Merge/delivery remains separate from source verification.
