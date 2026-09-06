# Worklog: GitHub 35

## Train map markers — entity-backed rewrite, 2026-08-05

The stale-marker failure was reproduced statically in the previous
`updateTrainBlips`: `_DOES_TRAIN_EXIST_ON_TRACK` selected a track index and
`_GET_TRAIN_POSITION_ON_TRACK` supplied a cached coordinate. No vehicle handle
backed the marker, and no entity-existence check could retire it. The installed
Train Tracker 1.1 used the same track-manager design; its configuration even
distinguished "unstreamed" coordinate blips, and its log repeatedly created
coordinate blips before a train entity materialized. That is why both versions
could leave a marker when streaming, mission cleanup or fast travel removed the
actual train.

`GameplayTweaks/modules/collectibles_map.cpp` now enumerates the current
ScriptHook vehicle pool and accepts only ordinary vanilla train-engine models
from extracted `vehicles.meta`: `northSteamer01x`, `privateSteamer01x`, and
`winterSteamer`. `trolley01x`, `steamerDummy`, and `GhostTrainSteamer` are
deliberately excluded. Each slot stores the live engine entity that owns its
blip. The marker is retired whenever tracking is disabled, the handle leaves
the current pool, the entity ceases to exist, or a reused handle no longer has
an accepted train-engine model. New markers can only be acquired from the
current live vehicle pool; no track, route, timetable, or cached position is a
source.

Markers use an entity-attached `BLIP_STYLE_TRAIN`. Extracted vanilla
`blipdata.ymt` defines that style with `BLIP_AMBIENT_TRAIN` art and
`BM_ShowHeading = Arrow`; `BLIP_MODIFIER_TRAIN_MISSION` changes its range to
always so the live train remains visible on the pause map. Rotation is refreshed
from the engine entity heading. Story Mode portability is evidenced by
`feud1.c`, where Rockstar refreshes a train blip with `SET_BLIP_ROTATION` from a
train-carriage entity heading.

Static checks passed: the rewritten function contains `worldGetAllVehicles`,
entity existence/model validation, entity-attached `BLIP_STYLE_TRAIN`, the
vanilla always-range modifier and heading refresh; it contains no calls to the
old track-active or track-position wrappers. `git diff --check` passed for the
owned module and this worklog. Per swarm policy, this feature agent did not
compile, link, install, or change GitHub state.

Runtime acceptance after integration build/install:

1. Approach an ordinary train: exactly one train marker appears, follows the
   locomotive and shows an arrow matching its direction of travel.
2. Let the train stream out or despawn: its marker disappears within the
   250 ms train polling interval and does not remain at the last coordinate.
3. During a train mission cleanup, confirm its marker disappears when the train
   entity is deleted and does not reappear from the still-active track.
4. Fast-travel while a train marker exists: no pre-travel marker survives; only
   a newly streamed, real train can acquire a marker afterward.
5. Saint Denis trolleys, the ghost-train discoverable and non-rendered dummy
   engines never receive train markers.

## Integration

GameplayTweaks built and installed with matching ASI SHA-256
`7E414A0625EC216CDD7147ADABEC6BFE7E7452EBCA95C42CE66FFCB2689E654A`.

The live test showed all markers disappeared. The three-name locomotive
allowlist was invalid for live variants. Enumeration now accepts Rockstar's
own `IS_THIS_MODEL_A_TRAIN` result and distinguishes the controlled locomotive
from its carriages by requiring a driver-seat occupant.
