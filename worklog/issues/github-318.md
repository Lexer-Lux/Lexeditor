# #318: Choose how Guardian Forces are acquired without Draw

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/318)

## Requirements and decisions

Read the live issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-23 misc-fixes: Lexer approved, tweak-vs-data answered, stays actionable

Lexer approved the rule (2026-09-23 comment) with two specifics: it must be a
tweak named "GF Acquisition Rework", and when on, drawable GFs cannot be
drawn — they are awarded automatically on winning the fight.

Answer to Lexer's question (tweak or data-file edit): a tweak. The existing
tweak layer already patches the same battle paths natively — see
`games/ff8/streamlined_draw.py` (Draw hooks/caves, no data-file edits) and
the shared Draw/Card command hooks in `battle_issue_54`. GF Acquisition
Rework follows the same pattern: a battle-victory award hook plus a Draw-list
filter for GF entries. No data-file edit is needed.

Next agent work:

1. Implement the tweak behind the standard tweak toggle with the approved
   name, reusing the Draw hook points and the GF-owned save path.
2. Cover award-on-victory, no-duplicate, Draw-suppression-only-for-GFs, and
   disable-keeps-GF with hermetic tests where the logic is separable.
3. Prove the battle-victory award and Draw suppression in game; source tests
   alone are not acceptance for this one.

Needs the game for step 3, so no implementation was written here. Issue stays
actionable.
