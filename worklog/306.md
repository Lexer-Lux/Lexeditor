# #306: Prepare a verified Better Targeting build

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/306)

## Requirements and decisions

Better Targeting removes the red Target labels from unselected actors and makes the selected target pointer fully opaque without changing target eligibility or command semantics. Acceptance must cover both single-target and group-target commands.

## Current implementation and evidence

The FFNx renderer/applicator implementation is present and integrated. During the 2026-09-06 audit, the supported Steam-English executable check exposed a verifier/applicator portability defect: source application depended on CRLF checkout bytes. PR #377 made the applicator newline-stable and merged as `3b72fed473aa590bd31b273fc9833e13b0d6902f`.

After that repair, the private supported-executable renderer replacement/old-hook verifier passed. The FF8-native Linux source job and Windows package/install job also passed, as did gameplay-settings persistence/composition. No visual in-game acceptance is inferred from those checks.

The live issue is now `untested` with a concrete multi-enemy player checklist.

## Next agent work

No implementation work is currently known. Keep the single-target opacity/label check, all-target marker check and unchanged targeting-behavior control from the live issue; reopen agent work only for a reproduced failure.
