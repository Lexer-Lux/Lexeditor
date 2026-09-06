# #144: Prepare a valid vanilla casing-ejection comparison

[Full request and discussion archive](github-144/conversation.md)

## Requirements and decisions

Recover the complete scope from the linked verbatim sources before implementation or status changes. The short GitHub summary is not the full specification. Do not infer that missing chat text was never supplied.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. This archive import makes no build, deployment or gameplay-success claim.

## Next agent work

Read the source records and preserve the latest explicit human corrections. Update this handoff, not a shared global Worklog.txt.


## 2026-09-06 — RDR2 isolated batch / session rdr2-issue-batch

### Implemented

The restore/blank operation covers the base weapon file plus all six authored
YMT overrides. Status aggregates all seven files and reports missing references
and records. Active install.xml replacement paths are respected, and all eleven
stack resources must be present. All trees are validated before writing,
including projectile-flag preservation in patch files. Caught late write/install
failures restore prior file bytes, mappings and cached roots. Existing .bak
files are retained. Power-loss recovery is not claimed.

### Agent checks

Synthetic regressions cover restore/reblank idempotence, mapped paths,
missing references/records/components, invalid flags, wrong input types,
traversal rejection and late save/install rollback. An isolated copy of the
actual project stack restored exactly 61 fields across seven files, then
reblanked exactly 61. Every other parsed XML field/attribute/tail was unchanged.
Original project/game files were not edited by that integration check.

### Remaining scope (not closed by this repair)

This repairs the invalid vanilla comparison setup; it does not calibrate custom
casing trajectories. Actual first/third-person, weapon-family and both-hands
visual/momentum comparisons and subsequent custom tuning remain actionable.
