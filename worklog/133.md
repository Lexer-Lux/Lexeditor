# #133: Establish whether hunting can start from independent tracks

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/133)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes disposition
No evidence proves usable trails persist without a live animal. A controlled trail and streaming experiment with the game comes before choosing native trails or custom signs. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side experiment/prototype
still owed), so flipping to waiting would be a fake checklist. Left
actionable until a real session can be written.

## 2026-09-23 agent review (per-game-rdr2): no new agent-side slice, stays actionable

Re-read the live issue plus comments. No evidence proves usable trails
persist without a live animal. Exact needs: a controlled trail/streaming
experiment with the game before choosing native trails or custom hunting
signs. No code written here.

## 2026-09-23 agent slice (impl/rdr2-actionables): controlled probe protocol

plugins/rdr2/hunting_tracks.py records the required probe as data
(trail lifetime after stream-out versus explicit deletion, tagged
identity, streaming conditions) and the two viable designs
(hidden/distant target ped, custom signs with later spawn) with
validate_track_experiment(), which rejects unevidenced native/custom
choices and vanilla tracks under near-zero density. Covered by
tests/test_rdr2_hunting_tracks.py (8 hermetic tests). No gameplay
claim: the probe and the design choice still need the game.

## 2026-09-23 agent slice (impl/rdr2-wave2): verified, no new code

Re-ran tests/test_rdr2_hunting_tracks.py: 8 green. No new agent-side slice was owed beyond the existing contract; the probe run and the design choice still need the game.
