# Radial ammo package and renderer repair — 2026-09-06

## Primary evidence and failure classes

Read central #194, its complete preserved discussion, the original mod #98 handoff, the actual RadialAmmoCounts package and GameplayTweaks/modules/radial_ammo_counts.cpp. Relevant prior failure classes: invented/incorrect resource routes, a diagnostic that proves intent instead of execution, preserving a rejected binding edit, and reporting installation without receipts.

The issue archive recorded three corrections that were missing from the GitHub snapshot: change the X/Y RawText binding rather than visibility (August 14), use CountBaselineY=7170 (August 19), and target widgets/0x51EA54CF.ymt plus widgets/0x6C358C77.ymt (August 20). The current source still had apps/ paths, a misspelled visibility binding and baseline 6500. Routes were recovered from recorded extraction evidence, not freshly re-extracted this session.

## Implemented in private runtime PR 211

- Version 0.2 manifest restores both recorded widgets routes.
- Exactly two bytes changed in sub_slot_list.ymt: offsets 4176 and 4301. Restored focusedEntrySubSlotItems.Size; replaced only the focusedEntrySubSlotItemCounterText RawText binding with its same-length disabled name. All four Size/visibility bindings remain intact. No opaque plate or new geometry was added.
- Restored CountBaselineY=7170 in source defaults and the matching INI, then regenerated the native menu schema.
- Converted GetPrivateProfileIntA's unsigned return to signed int before floating-point scaling of NudgeX/NudgeY. Negative offsets previously became huge positive coordinates.
- Added effective baseline/offset values to the existing bounded heartbeat; corrected its documented log destination to GameplayTweaks.log [radial-counts].
- Replaced the obsolete verifier that required the rejected visibility edit and unavailable external vanilla files. The new verifier reads the exact two package resources, manifest, sizes, RBF headers, binding counts and SHA-256 values without writing the package.
- Windows artifacts now include the matching ASI and lml/RadialAmmoCounts resources, with installation/rollback notes. They deliberately exclude the user's whole INI and the SDK.

## Execution evidence

Six tests compile and execute the entire actual production renderer against synthetic native state: baseline/spacing, signed offsets, live reserves/zero-stock text, two-second hot reload, display gates, and ultrawide spacing. The old production source failed baseline and signed-offset cases; the repaired source passed all six.

Seven package tests passed: reviewed candidate/read-only behavior, obsolete paths, byte corruption, rejected visibility regression, extra resource, missing resource and traversal. Existing binocular prompt/retirement/development-mode checks also passed. The importer SHA-256 compared the generated production source, INI, header, package resource and all three test scripts against locally tested bytes before committing.

Private source commit ec177b9774b32b11a322903bd1d4b40588d95286; CI/package commit ca2cfb6229e06f4cfd316614d95f5b84077cde90. Source run 34044885506 and Windows release/development run 34044885479 completed successfully. These are source/build checks, not installation or gameplay acceptance.

Resource SHA-256:
- ammo_counter.ymt unchanged: b299b06a8a4448f23c6f17d57e78b027f3988e8b9b90b9c3e1fbfb5e63379969
- repaired sub_slot_list.ymt: bd9facdbde0871c4471c09b00727b11be2d220b6f16d40b1edb325b58b986961
- pre-repair checked-in sub_slot_list.ymt: bbc892d3aa328034954aae8c23eb6de53dcff82185549a7bfe09d7635d79592f

## Still open

No game launched or installed files changed. Successful actual VFS replacement records, screenshots showing X/Y absent, and mouse/controller/bow/shotgun acceptance remain. The overlay dims zero-stock text only; dimming the native icons is not implemented by this repair. This broad issue remains actionable. The README explains backup/rollback and how to update only a superseded baseline without overwriting tuned settings.
