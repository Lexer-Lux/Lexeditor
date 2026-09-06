# Worklog: 060 112 Streak 42 Worn State Latch 2026 08 04

## #112 streak + #42 worn-state latch — 2026-08-04

Build `AD3CA634779E9E196ED7254769A5268186EEF4CD49F73544DC6649DB63E284EE`.

#112. The corona was `_DRAW_MARKER(0x94FDAE17)` five times along the path plus
`DRAW_LIGHT_WITH_RANGE` — a chain of spheres with a point light. That is a
headlight, hence the report. RDR2 exposes NO DRAW_LINE (absent from the SDK
header and from every decompiled script), so a line cannot be drawn directly.
New mode 3 `streak` draws ONE `MARKER_TYPE_CYLINDER` at the midpoint of the
tail->head segment, scaled thin on X/Y and to the segment length on Z, with the
projectile direction passed as the marker direction so it orients along travel.
No point light at all. `[ProjectileVisibility] Mode=streak`, tunable
`StreakLength` (default 2.60) and `StreakWidth` (default 0.035). Mode 2 corona
retained. Mode 1 engine_tracer left in place but is a no-op — see the earlier
entry.

#42 check mark. `INVENTORY_SET_CLOTHING_ACTIVE` was fed `wornRoute ==
selectedRoute`, where `wornRoute` comes from scanning 39 metaped component slots
at `getGlobalPtr(1946804 + 1498 + slot*3)`. That single source was wrong in both
directions across two builds — stuck ON, then stuck OFF. Added
`maskWornRouteLatch`, set at `START_ITEM_INTERACTION` time from the MASK_ON/
MASK_OFF state we ourselves issue (the `worn` value there is pre-interaction, so
the latch takes its inverse). Resolution is `scan || latch`, and a positive scan
re-syncs the latch. Every change of the resolved value logs scan/latch/wornRoute/
selectedRoute/bandanaWorn to `GameplayTweaks.carried-mask.log`, so if it is still
wrong the next session identifies the failing source instead of guessing.

#103 acquisition feed: NOT touched this build, deliberately. `INVENTORY_ADD`
already passes `ADD_REASON_DEFAULT` (verified as what 1062 game scripts use;
`ADD_REASON_NOTIFICATION` was fabricated and is gone). Both silent items — empty
bottle and casings — also had no icon because their texture dictionary was never
loaded, which is now fixed. Retest before adding a synthetic UIFEED notification,
or a working native feed and a fake one will both fire.

