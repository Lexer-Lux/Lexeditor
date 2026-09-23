# #171: Prepare an irreversible drowning presentation prototype

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/171)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes disposition
Research only. The controlled drowning-time prototype is not built; zero-second and trough-animation proposals stay rejected. The prototype plus recovery checks come before any new drowning test. Death at zero stamina stays inevitable with no rescue window or HUD warning. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side filter/asset/
prototype still owed), so flipping to waiting would be a fake checklist.
Left actionable until a real session can be written.

## 2026-09-23 agent review (per-game-rdr2): no new agent-side slice, stays actionable

Re-read the live issue plus comments. The controlled engine-owned
drowning-time prototype is still unbuilt; zero-second and trough-animation
proposals stay rejected. Exact needs: build that prototype with recovery
checks, then a Lexer drowning session. Death at zero stamina stays
inevitable with no rescue window or HUD warning. No code written here.

## 2026-09-23 agent slice (per-game-rdr2): prototype shape contract

games/rdr2/drowning_prototype.py records the agreed shape as data plus
validate_drowning_plan(), which requires the irreversible zero-stamina
latch, presentation with no rescue window or HUD warning, immediate-death
fall-throughs (shallow, ragdoll, unsafe first person, mission, refused
control), recovery checks, and rejects zero-second and trough proposals.
Covered by tests/test_rdr2_drowning_prototype.py (9 hermetic tests).
No gameplay claim: building the prototype still needs the game.

