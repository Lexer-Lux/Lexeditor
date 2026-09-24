# #107: Turn unique guns into reusable customization parts

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/107)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes disposition
Schofield prototype proposed; component and engraved-mesh compatibility unproven. A working example comes before design or gameplay review. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (prototype/research still owed on
the agent side), so flipping to waiting would be a fake checklist. Left
actionable until a real session can be written.

## 2026-09-23 agent slice: checkable Schofield conversion plan

plugins/rdr2/unique_gun_parts.py records the first proof candidate (unique
Schofield features as grip/barrel/frame components on the base Schofield,
with catalog and gunsmith entries and pickup-unlocks-parts) plus
validate_prototype(), which rejects stat-toggle-only parts, missing
entries, uncovered in-game checks, and unowned engraved-mesh assumptions.
Covered by tests/test_rdr2_unique_gun_parts.py (11 hermetic tests).
No gameplay claim: gunsmith visibility, installation, persistence, dual
wield, mission rewards, and compendium credit still need a real session.

## 2026-09-23 agent slice (impl/rdr2-wave2): session checklist

plugins/rdr2/unique_gun_parts.py gains INSTALLATION_CHECKLIST (each of
the six verifications expanded into ordered steps with explicit pass
criteria) plus validate_installation_plan(), which requires full
six-verification coverage, ordered actions, and pass criteria per step.
Covered by 7 new tests in tests/test_rdr2_unique_gun_parts.py (18 total,
green). No gameplay claim: the session itself still needs the game.
