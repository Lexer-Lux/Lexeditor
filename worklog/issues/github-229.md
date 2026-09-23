# #229: Reduce plant density without leaving unusable plants

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/229)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes finding
Animal density multipliers exist (animal_density.cpp) but cover animal spawns, not plants. The scenario-point disable failed by leaving unpickable plants, and a real placement or spawn solution needs research with the game. No candidate to test. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (engine research/agent-side
candidate still owed), so flipping to waiting would be a fake checklist.
Left actionable until a real session can be written.

## 2026-09-23 agent review (per-game-rdr2): no new agent-side slice, stays actionable

Re-read the live issue plus comments. The scenario-point disable stays
rejected (visible unpickable plants) and animal-density multipliers do not
cover plants. Exact needs: engine placement/spawn research with the game
and a real candidate to test. No code written; recording the needs here
instead of inventing a spawn hook.

## 2026-09-23 agent slice (per-game-rdr2): candidate contract

games/rdr2/plant_density.py pins the acceptance boundary as code plus
validate_density_candidate(), which requires a named placement/spawn
mechanism with a density target and pickability proof, and rejects the
scenario-point-only disable and animal-multiplier substitution. Covered
by tests/test_rdr2_plant_density.py (7 hermetic tests). No gameplay
claim: engine research and a real candidate are still owed.

## 2026-09-23 agent slice (impl/rdr2-wave2): verified, no new code

Re-ran tests/test_rdr2_plant_density.py: 7 green. No new agent-side slice was owed beyond the existing contract; engine research and a real candidate are still owed.
