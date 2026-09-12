# #277: Verify delivery of real cutscene suppression for Recon

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/277)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-08 current candidate review

Live issue body and comments were read. Full scope is to suppress Recon displays and acquisition during actual Story cutscenes and retain completed tags for normal play afterward. Cinematic camera mode alone does not satisfy this.

The current source uses the three terms from the game's overlay predicate: HUD hidden, cinematic camera, and an existing/running animation scene from Global_43800. The early return precedes compendium study updates, target maintenance, drawing, acquisition and new scans. It clears partial observations and prompts, while retaining completed target collections. This source was included in the verified combined development build `8AE9385498F96437AFB504381F6B8E34491E3A740D8993C539D89C21B3D7BB2E`; that candidate is held under `out/rdr2-after-duration`, not installed while #151 is active. The executable `tools/verify_rdr2_recon_cutscenes.py` passes and rejects six intentional regressions. It verifies all three causes independently, partial-progress reset, completed-tag retention, early return before downstream work, and normal resumption. SDK native hash CBFC7725DE6CE2E0 uses the older STARTED alias and current RUNNING name for the same Global_43800 predicate. This is branch execution with controlled natives, not a rendered Story test.

Delivery and acceptance remain open. After the duration experiment is restored and the reviewed normal candidate is installed, use the existing enabled Recon controls to tag a nearby persistent target, then enter an actual mission Story cutscene. Confirm no Recon markers, progress display or acquisition appear during it; cinematic-camera-only testing is insufficient. After control returns, surviving in-range targets should retain their tags, while interrupted partial study must restart. Repeat with a HUD-hidden scene and the ordinary cinematic camera. Report the scene/mission, before/during/after captures, and the `[recon]` records from `GameplayTweaks.log` beside the installed ASI. A target removed by the game itself is not evidence that Recon deleted a tag.

The current heartbeat is sampled every five seconds. Absence of a suppression record during a shorter scene does not prove the guard failed; visual behavior remains the acceptance boundary. Do not ask Lexer to repeat the failed test before the normal candidate is delivered.
