# #156: Allow card sales only after the set is mailed

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/156)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #57 worklog](github-156/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-57.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 card conversion transaction repair

Live #156 and retained original request reread. All12 sets must stay locked until
mailing; later copies can become sale records without restoring submitted cards.

Found a concrete failure in duplicate_cigarette_cards.cpp: if original removal
and rollback both failed, the next update granted another resale copy. Native
return flags were also trusted ahead of counts, so a false flag after an actual
write could leave duplicated or lost value. Conversion now uses inventory count
readback and holds a pending rollback before any further provisional grant.
A pending rollback is also serviced when the feature is disabled.

Executable evidence: tools/verify_rdr2_duplicate_card_transactions.py executes the
production C++ module with controlled inventory calls in a cleaned temp directory.
It checks unmailed lockout, all12 mailed states/144 cards, empty/full conditions,
false-return successful writes, repeated rollback failure without extra grants,
and recovery. Three regression mutations are rejected. The original #57 data
verifier also passes:144 originals locked,12 sale records and fence routing valid.
No catalog edits were required or made. No build/install/game launch ran.

Recurrence audit:
- Failure class: non-atomic inventory transfer; repeated grants after failed undo.
- Prior evidence: existing #57 grant-before-remove contract; current count checks
  and rollback result were insufficient. Prior failure notes prohibit data loss.
- Invariant: no new resale grant while a prior provisional grant remains pending;
  count readback decides whether ownership actually changed.
- Mechanism: one pending resale hash and baseline count; settle before conversion.
- Coverage: executable native-failure matrix and3 source mutations; original data
  verifier passes. No runtime/visual acceptance is claimed.
- Residual risk: synchronous native/count behavior and real post-office/fence flow
  still need game acceptance on a disposable pre/post-mail save. This source fix
  is not a delivered candidate and #156 remains actionable.

## Local delivery, 2026-09-08

Development build passed. Installed ASI and matching release manifest with RDR2 closed; SHA-256 `EC0ECC477BE9089E3C17C25816580FD85D597A113236C94B3041E0E3504819E2`. Previous ASI retained as a small hash-named rollback copy. No catalog or settings changed. Production executable tests pass; rejected four train regressions and three card-conversion regressions. No game launch or rendered acceptance claimed. Full issue remains actionable.
