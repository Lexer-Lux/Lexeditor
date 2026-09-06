# #192: Deliver gradual decay of unfinished Recon progress

[Full request and discussion archive](github-192/conversation.md)

## Requirements and decisions

Incomplete Study/tag progress must drain gradually after losing the target. Completed tags must remain complete. The rate is configurable; zero pauses decay.

## 2026-09-06 — clean follow-up runtime candidate

The prior “source-only” status was stale: current runtime `master` still deleted partial ped dwell after target loss and had no decay setting. Runtime PR [Lexer-Lux/Lexers-Mod-For-RDR2#212](https://github.com/Lexer-Lux/Lexers-Mod-For-RDR2/pull/212) now stores explicit partial progress for peds and plants. Visible targets accumulate progress; after a 150 ms loss grace, incomplete progress decays at `StudyProgressDecayPercentPerSecond` (default 50% of a full bar per real second). Setting 0 pauses decay. Completed tags remain outside this partial-progress state and do not decay.

Permanent `verify_recon_scaling_decay.py` guards the retained progress/decay path and rejects the old instant-erasure state. Source CI run 34050295438 passed. Both release and development Windows variants built and packaged successfully in run 34050295402. A production compiler error found during the first build attempt (`observedPlantAt` stale reset) was repaired before these green runs.

## Acceptance boundary

No game installation or visual/gameplay acceptance is claimed. Test a partial ped Study, a partial plant Study, decay at the default rate, `0` decay preserving partial progress, and a completed tag remaining complete. Preserve the user's existing INI when installing the candidate.
