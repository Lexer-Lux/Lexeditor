# #153: Deliver collectible bottles and remove obsolete settings

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/153)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-06 — obsolete synthetic bottle feed removed completely

The live runtime contradicted this issue's earlier status: `ForceAcquisitionFeed`, its config reader/state, custom `drawGrantFeed`/`announceItemGranted` fallback and generated-menu exposure were still present. The preserved discussion explicitly superseded that fallback in favor of Rockstar's real acquisition feed.

Removed the fallback implementation, the complete four-line INI block, obsolete schema metadata and generated menu row. A first cleanup attempt exposed two stale verifier totals; a second exposed that deleting only the key would incorrectly attach the old #103 comment to `BlockWeaponActions`. Both were rejected before product commit. The final cleanup removes the whole block and updates the lifecycle/menu contracts deliberately.

Runtime product commit: `b33e540ac6392bab73c174248f1eb8d8402cc76f`. Verification confirms `ForceAcquisitionFeed`, `announceItemGranted` and `drawGrantFeed` are absent from runtime/config/generated-menu sources; settings generation is reproducible and existing cigarette-card/casing checks remain green. Permanent-CI follow-up: `0fbc622a2010658e08776be2e77b4214dcf2cedc`.

This completes the obsolete-setting/fake-feed removal slice. It does not prove collectible bottles or the real Rockstar feed behave correctly in-game; retain the broader issue until the final candidate is installed and its bottle behavior is accepted.
