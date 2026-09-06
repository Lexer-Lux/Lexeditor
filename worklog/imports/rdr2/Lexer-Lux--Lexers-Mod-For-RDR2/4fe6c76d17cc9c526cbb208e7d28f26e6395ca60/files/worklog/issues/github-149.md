# GitHub #149 - Activated Campfire Blip With No Physical Camp

## Live report and preserved evidence

The issue screenshot shows two `Activated Campsite` campfire glyphs around
Valentine; Lexer reported that one has no camp at its location. The live issue
has no follow-up comments.

The installed `campsites.csv` contains 14 authored rows, four persisted with
`activated=1`, including two active Valentine-area rows. The installed unified
log records only intent:

- session start loaded all 14 sites;
- `player_camp` thread 103 was started for site 0;
- thread 3209 was started for site 2;
- site 0 was later started again as thread 6580.

There was no physical-object readback or activation transition in that build.
A successful `START_NEW_SCRIPT_WITH_ARGS` return therefore proved only that a
thread was created, not that its campfire or camp props existed.

## Exact source defect

The saved `Campsite::activated` bit was used directly for the lit blip and death
respawn eligibility. The activation prompt required only proximity, inactive
state, and player control. It did **not** require the physical `player_camp`
fire, so a rejected/slow/materialization-blocked camp could be activated on bare
ground and persisted forever as a lit marker.

The materializer also treated either its tracked thread **or any**
`SCRIPT_REFS("player_camp")` result as proof that the requested site was already
materialized. When the tracked thread had ended but another/reference-counted
`player_camp` instance remained, that early return occurred before the dead
thread handle was invalidated. The saved site was then left marked as
materialized without a physical camp and no new launch was attempted.

## Primary Story evidence

`player_camp.c` establishes a precise physical postcondition:

- `func_69` assigns `P_CAMPFIRE02X_COMBO` to the campfire model field;
- `func_107` calls `OBJECT::CREATE_OBJECT_NO_OFFSET` for that model at
  `uParam0->f_4`, the camp origin;
- the authored campsite integration supplies the saved row coordinate through
  the explicit-position launch path.

Consequently an existing `P_CAMPFIRE02X_COMBO` within 1.5 metres of the saved
origin is a stronger postcondition than thread creation or a generic script
reference.

## Narrow repair

`GameplayTweaks/modules/world_economy.cpp` now:

1. considers the current site already materialized only while its own tracked
   `g_campThread` is active; an unrelated `player_camp` ref no longer satisfies
   that ownership check;
2. invalidates a dead tracked thread before applying the generic script-ref gate;
3. reads back the exact `P_CAMPFIRE02X_COMBO` at the saved origin;
4. requires that physical fire before the activation prompt can become usable;
5. while the player is within the existing 30-metre authored footprint, emits
   one-second missing-state heartbeats with tracked site/thread/ref data;
6. allows a full 15-second local streaming/materialization grace period, then
   clears a persisted activation, refreshes the marker to inactive, and saves
   the corrected row if the fire is still absent;
7. logs both physical verification and activation after verification.

The repair deliberately does not delete the authored campsite row or its blip.
Far camps intentionally have no streamed entities, so absence is evaluated only
while the player is within 30 metres. A failed active site is demoted to a
recoverable inactive campsite; it can be activated again only after the real
campfire exists. This avoids destroying a valid saved location because of a
temporary streaming miss while eliminating the false `Activated Campsite`
claim.

## Static checks and integration

`python tools/reverse-engineering/verify_campsite_presence_issue_149.py` checks
the authoritative model/create path, exact-origin object readback, local-only
15-second grace, heartbeat and demotion persistence, physical activation gate,
dead-thread ordering, removal of generic-ref false ownership, and preservation
of the authored row.

`python tools/reverse-engineering/verify_campsites_issue_116.py` also still
passes, preserving the 30-metre removal/duplicate-prevention contract, launch
backoff, live 14-site separation, and earlier fixup cleanup.

No dispatcher or config change is required because this is a narrow correction
inside the existing `updateCampsites` path. The integration owner only needs to
carry the modified `GameplayTweaks/modules/world_economy.cpp`, verifier, and this
worklog into the combined build. No shared `script.cpp`, INI, manifest, build,
install, or GitHub label was changed here.

## Runtime boundary

After integration and install, visit the reported ghost marker and remain
inside 30 metres. The log must either show `physical camp verified`, in which
case activation remains legitimate, or show uninterrupted missing heartbeats
followed after 15 seconds by `demoted false activation`; the map label/icon must
then become inactive and the CSV row must persist with `activated=0`. At a real
inactive campsite, the activation prompt must remain hidden until the physical
fire exists, then activation must light the marker and log the verified fire
handle.
## 2026-08-10 installed release

- Included in release ASI `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
- The game-root ASI and required payloads were hash-verified. The open issue moved from actionable to test me; the on-site physical-fire verification/demotion remains runtime acceptance.
