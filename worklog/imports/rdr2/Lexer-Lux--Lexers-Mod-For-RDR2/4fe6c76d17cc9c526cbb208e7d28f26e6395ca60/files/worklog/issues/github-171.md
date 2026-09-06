# GitHub #171 - Campfires Come Activated

## Failure classes checked before the repair

- **Fabricated constants or evidence:** both campsite models and their creation
  order were resolved in the extracted Story script before use. No model name,
  flag, or launch mode was inferred.
- **Intent mistaken for a postcondition:** a successful `player_camp` thread
  start is not proof of the saved activation bit, the correct marker, or a live
  object. The repair reads back the owned inactive object and keeps the existing
  active-fire presence checks.
- **Fighting the engine per frame:** the inactive state owns one frozen Rockstar
  object. It does not start the full camp and then try to disable its prompts or
  features every frame.
- **Regression boundary:** campsite removal and #164 teardown suppression stay
  on their existing F3/owner paths. The repair deletes its own inactive object
  before removing a saved row and does not change the F3 hold duration.

## Exact mismatch

The saved row was value-initialized with `activated=0`, and its marker therefore
used the inactive icon. The same F3 release immediately called
`materializeCampsite`, which started Rockstar's `player_camp` script regardless
of that bit. That script creates the complete usable camp. The map state and the
physical state therefore described different things.

The installed trace preserves the mismatch. Recent F3 placements started
`player_camp` for sites 14 and 15, then logged `presence begin ... activated=0`.
The current installed CSV contains 16 rows: 3 active and 13 inactive. The user's
visible report supplies the missing player-facing postcondition: the newly
placed physical camp was already usable while its marker remained inactive.

## Primary Story evidence

`_downloads/RDR2-Decompiled-Scripts/script_rel/player_camp.c` owns both states:

- line 2821 assigns `P_CAMPFIREBURNTOUT02X` as the burnt-out model;
- line 2822 assigns `P_CAMPFIRE02X_COMBO` as the lit model;
- lines 4560-4561 create and freeze the burnt-out model at the camp origin;
- line 4567 then creates the lit combo as part of full `player_camp` startup.

The existing integration always ran through the last step. There is no separate
inactive full-camp launch flag in the proven path.

## Repair

An inactive saved site now owns only one mission-managed
`P_CAMPFIREBURNTOUT02X` at its authored coordinate. The materializer returns
before `player_camp` starts. It records a successful object readback and keeps
the inactive marker and saved `activated=0` state.

Holding the existing Activate Campsite prompt removes that owned burnt-out
object, persists `activated=1`, changes the marker, and then launches the full
Rockstar camp. Moving out of the 120-metre materialization range removes the
transient inactive object but not its saved row or map marker. F3 long-hold
removal deletes the inactive object before erasing the row.

## Verification and runtime boundary

`python tools/reverse-engineering/verify_campsite_activation_issue_171.py`
checks the exact Story models and creation order, the return before script
launch, the inactive placement state, the activation swap, and preservation of
the F3 hold and teardown-protection calls.

The adjacent #116, #149, #163, #164, #1, and #122 verifiers must still pass.
Static checks cannot establish presentation or interaction. After integration,
build, install, and restart, runtime acceptance is:

1. Tap F3 in a valid area. Only the burnt-out campfire appears, the map marker
   stays inactive, and no sleep/cook/craft/fast-travel interaction is available.
2. Hold Activate Campsite. The full usable camp replaces the burnt-out fire,
   the marker changes to active, and the saved row becomes respawn-eligible.
3. Hold F3 at both an inactive and active authored site. Each physical state,
   its marker, and its CSV row are removed without `ERROR:FFFFFFFF`.

The combined compile, install, and player-visible checks remain pending.
