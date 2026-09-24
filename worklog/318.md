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
`plugins/ff8/streamlined_draw.py` (Draw hooks/caves, no data-file edits) and
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

## 2026-09-23 per-game-ff8: separable logic landed, native proof still needs the game

Landed on branch per-game-ff8: new `plugins/ff8/gf_acquisition_rework.py` owns
the approved acquisition map (6 drawable GFs with primary + Disc 4 recovery
bosses), award-on-victory with no-duplicate, Draw-list GF suppression with
spells untouched, and disable-keeps-GF (awards only append). Activation fails
closed (`GF_ACQUISITION_AVAILABLE = False`) until battle-victory/Draw-list
hooks and GF-owned save offsets are proved; no guessed bytes. Wired as a
visible-but-blocked tweak (`gfAcquisitionRework` in gameplay_settings +
boot.js row) mirroring the issue-90 pattern. Covered by
`plugins/ff8/gf_acquisition_rework_test.py` and
`tests/test_ff8_gf_acquisition_rework.py`; full ff8 unit set green (223
passed, 3 skipped).

Still needs Lexer/game: prove the battle-victory award and Draw suppression
in game (source tests alone are not acceptance); native hook research
(battle-victory point, Draw-list filter point, GF-owned save path) to flip
the availability gate.

## 2026-09-23 impl/ff8-actionables: verified, no new code

Re-verified on this branch: `games/ff8` logic stands as merged
(`plugins/ff8/gf_acquisition_rework.py`, gated, tests green in the ff8
unit run). No new agent-side slice exists: flipping the availability
gate needs proved battle-victory/Draw-list hooks and GF-owned save
offsets from the game. Stays actionable.

## 2026-09-23 impl/ff8-wave2: native anchors recorded, gate stays closed

Added a native-anchors comment to `plugins/ff8/gf_acquisition_rework.py`:
GF-owned state is ff8_externals.savemap->gfs[gf_idx].exists bit 0 with the
native GF table at 0x01CFDCA8 + gf * 68 (both from the vendored FFNx
derivative sources), and Draw-list suppression reuses the proved
streamlined_draw.py hooks. `tests/test_ff8_gf_acquisition_rework.py` and
the module test stay green (18 passed). The availability gate stays closed:
the battle-victory trigger routine is still unidentified, so no award bytes
were written. In-game proof plan: one save per primary boss (6) plus Disc 4
recovery checks (7), no-duplicate ability check, Draw-list GF absence with
spells intact, disable-keeps-GF. Stays actionable.
