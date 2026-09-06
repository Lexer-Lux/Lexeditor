# #181: Make binocular transition speed actually change

[Full request and discussion archive](github-181/conversation.md)

## Requirements and decisions

Recover the complete scope from the linked verbatim sources before implementation or status changes. The short GitHub summary is not the full specification. Do not infer that missing chat text was never supplied.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. This archive import makes no build, deployment or gameplay-success claim.

## Next agent work

Read the source records and preserve the latest explicit human corrections. Update this handoff, not a shared global Worklog.txt.


## 2026-09-06 — RDR2 isolated batch / session rdr2-issue-batch

### Current decision and paired runtime candidate

The latest explicit request permits removing the ineffective speed control.
The public schema hides legacy TransitionAnimRate/TransitionAnimLayer entries
so stale external INIs cannot present them as useful settings. The paired
private branch fix/lexeditor-rdr2-issue-batch removes the runtime observer,
animation-speed setters, config/default and generated menu row. The native
satchel swap, draw/stow timing, latch and camera-readiness paths remain intact.

The runtime schema is regenerated against that repository's own matching
schema, not overwritten with a newer public schema that would retune unrelated
menu rows. The obsolete legacy probe verifier now asserts the explicit
retirement acceptance instead of requiring the rejected control.

Source/unit checks pass. No ASI build/install or visible animation-speed
improvement is claimed. The crash in #357 still blocks an in-game comparison.
