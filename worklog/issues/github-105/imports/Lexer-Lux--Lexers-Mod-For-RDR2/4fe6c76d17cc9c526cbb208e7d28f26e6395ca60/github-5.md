# GitHub #5 - On-belt lantern

## Current attempt

The vanilla-only fallback failed in-game. Restoring the Davy and electric
lantern radial records let Arthur select a lantern, but he kept it in his hand.
That did not provide the requested belt lantern. Issue #5 returned from
`test me` to `actionable` after this report.

The replacement kept the exact vanilla radial records but restored the custom
belt module with different ownership rules:

- The belt prop persisted while unlit. Time and interior state no longer
  created, lit, or removed it.
- A rising edge from Rockstar's selected lantern weapon toggled only the belt
  light. The same selection also queued the Story Mode weapon-stow sequence.
  The sequence waited until script task `716706914` was idle, so it did not
  fight the lantern draw task.
- The normal, Davy, and electric weapon hashes selected their matching
  `s_interact_lantern01x`, `02x`, and `03x` models.
- The attachment resolved `Gun_GripR` on the prop and `PH_R_Hip` on the player
  by name. Missing bones deleted the created prop and logged a hard failure.
- The attachment used native `0xB629A43CA1643481` with the complete 22-argument
  RDR2 contract and the constraint tail used by
  `beat_treasure_hunter.c:1000`. Native `0xB6CBD40F8EA69E8A` created the object
  skeleton first, as in `campfire_gang.c:53661-53662`.
- Prop collision stayed enabled for the world. Only the prop/player pair had
  collision disabled. A 4 Hz attachment readback removed a detached prop or a
  prop more than 1.25 metres from the right hip.
- Mission, death, swimming, and ragdoll gates removed only the mod prop. The
  module did not intercept a mission lantern.
- The unified log recorded gates, radial toggles, deferred and issued stows,
  stow readback, attachment failure, displacement failure, and a three-second
  idle heartbeat.

## Primary-source evidence

- `_downloads/extract/common_0_data/ai/defaultcarriablesdata.meta:1264-1274`
  mapped the three lantern models to the three weapon items.
- The same file at `6286-6302` assigned the lanterns to right-hand grip
  `ID_GUN_GRIPR`.
- `_downloads/rdr3_discoveries/boneNames/player_zero__boneNames.lua:464`
  resolved `PH_R_Hip` as player bone ID 60844. The old numeric ID 11816 was not
  present in that skeleton.
- `_downloads/natives.json:18383-18479` resolved the RDR2 physical-attachment
  native and all 22 arguments.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/beat_treasure_hunter.c:1000`
  physically attached a carriable by named prop and owner bones.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/campfire_gang.c:53660-53663`
  created an object skeleton before a physical attachment to a ped.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/act_camp_fff_light.c:3004-3005`
  set both light-weapon attach points to `WEAPON_UNARMED`.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/electric_lantern.c:84-89`
  read the current lantern weapon at attach point 0.

## Integration and acceptance boundary

This attempt changed only the issue-owned module, INI section, and worklog.
The integration task owns the combined build, installation, hash verification,
and GitHub transition to `test me`.

The code and source evidence do not prove the physical pose in-game. Runtime
acceptance still requires:

1. The unlit lantern hangs at the right belt and does not stay in Arthur's hand.
2. Each radial selection toggles the belt light once and returns Arthur from
   the hand-held state.
3. Walking, sprinting, turning, crouching, mounting, and stopping do not cause
   deep clipping, jitter, player movement, detachment, or a flying prop.
4. A Story mission lantern is not intercepted.
5. `GameplayTweaks.log` contains the idle heartbeat, radial edge, stow issue,
   stow readback, and attachment state. A missing bone or failed constraint is
   reported as a failure, not as a successful attachment.

## Combined build

The integration verifier passed all 34 belt/radial contracts and the combined
release compiled successfully. Queued ASI SHA-256:
`AEAE1D1D1C53861A6F507815030957D333E77D097E9F2E7F899EF5B2FF82B2A3`.
RDR2 was running, so installation remained pending.

## 2026-08-10 returned-test repair: downward pose

The installed physical-constraint replacement fixed the original hand-held
failure, but Lexer's screenshot showed the remaining pose defect precisely:
the lantern body pointed behind Arthur instead of toward the ground. The
installed log simultaneously showed a live, healthy prop (`prop=165378`,
`spawnFailure=0`) across repeated heartbeats and no detach/displacement failure.
The mechanism and bone resolution were therefore executing; the zero local
rotation on the constraint was the remaining cause.

The physical attachment now applies a +90-degree local-X rotation. In RAGE's
entity axes that maps the observed rearward long axis onto local -Z, so the
lantern hangs downward. Named `Gun_GripR` / `PH_R_Hip` bones, offsets, skeleton
creation, collision policy, physical constraint tail, radial behavior, and all
safety gates are unchanged. The spawn record now includes
`localRotation=90,0,0 hangAxis=-Z`, so the installed log identifies the exact
pose variant being tested. The #5 verifier requires both the constant and its
placement in the physical-attachment rotation triplet.

This was an issue-local source/static repair only. Runtime acceptance still
requires Lexer to confirm that the lantern body points down at rest and remains
stable while walking, sprinting, turning, crouching, mounting, and stopping.
The radial toggle/stow and mission-suppression checks remain required as listed
above. No build, installation, shared dispatcher/INI/manifest edit, or GitHub
mutation was performed in this pass.
## 2026-08-10 combined release

- Release ASI built successfully: `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`.
- RDR2 was running, so one hidden payload-only installer was queued. The issue remained actionable pending game-root hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.

## Recurrence audit before the returned `+90 X` repair

This audit was written before changing the returned source, after reading
`fuckups.txt`. The previous `+90 X` explanation was not primary-source
evidence: it inferred a model axis from one screenshot, changed the constraint,
and asserted a `hangAxis=-Z` postcondition that no native readback or model data
had established. The installed log proves only that the constraint executed and
remained attached. Lexer's next test (lantern no longer visible / apparently
inside the body) is the player-visible disproof. That transform is now recorded
as a failed speculative guess and cannot be used as evidence for another axis.

### Primary evidence/reference

- Player skeleton authority:
  `_downloads/rdr3_discoveries/boneNames/player_zero__boneNames.lua`; both the
  internal physical hip and named belt/collision anchors must be checked before
  choosing the owner attachment point.
- Carriable authority:
  `_downloads/extract/common_0_data/ai/defaultcarriablesdata.meta`; the lantern
  reach/grip bone is `ID_GUN_GRIPR`.
- Physical-constraint signature and sanctioned call-site authority:
  `_downloads/natives.json` plus the opened
  `_downloads/RDR2-Decompiled-Scripts/script_rel/beat_treasure_hunter.c` call.
- Execution evidence:
  installed `GameplayTweaks.log` contains repeated `prop spawned` and attached
  heartbeats with no detach/displacement failure. It contains no model-basis,
  bone-basis, mesh-bounds, or post-constraint orientation readback. Therefore
  it cannot prove any rotation or visible pose.
- The question whether one script-drawn lantern light can ignore only the
  player body's shadow/occlusion is **unknown at this audit point**. No native,
  renderer flag, entity-light exclusion mask, or opened Story call site has yet
  been resolved. No fake support claim or unproven invocation is authorized.

### Sanctioned path and execution proof required

The sanctioned attachment remains one skeleton creation plus one named-bone
physical constraint per prop spawn/owner change, with world collision enabled
and only the prop/player collision pair disabled. Any pose change now requires
one of: resolved model/constraint axes from primary data, or an explicit bounded
calibration mechanism whose variants and readbacks are logged and deliberately
selected in-game. `IS_ENTITY_ATTACHED_TO_ENTITY` and displacement prove the
joint executes; only Lexer's view proves the lantern is outside the coat, at the
right belt, and hanging downward.

### Player-visible acceptance

At rest and through walking, sprinting, turning, crouching, mounting and
stopping, the full lantern must remain visible outside Arthur/John's right belt,
its body hanging toward the ground rather than backward or into the torso. The
radial must toggle the light once and stow the held lantern. Light coverage and
body occlusion are separate visual checks and cannot be claimed from a draw
call or attachment heartbeat.

### Every issue-owned per-frame native before this repair

Although the old source comment said the light draw was the only per-frame
native, `updateBeltLantern` actually also queried
`PED::IS_PED_DEAD_OR_DYING`, `PED::IS_PED_SWIMMING`, and
`PED::IS_PED_RAGDOLL` every frame. When lit it additionally called
`ENTITY::DOES_ENTITY_EXIST`, `ENTITY_COORDS` and
`GRAPHICS::DRAW_LIGHT_WITH_RANGE` every frame. Weapon selection was bounded to
20 Hz; attachment/bone/displacement health to 4 Hz; spawn attempts to 4 Hz;
the heartbeat to one per three seconds. The repair must either justify these
cadences explicitly or transition-cache/rate-limit everything except the
frame-scoped light draw.

## Returned-test repair: bounded pose calibration and exterior belt anchor

The failed hard-coded `+90 X` pose was removed. No replacement angle is claimed
from the screenshot. The source now resolves Arthur's extracted `CP_R_Belt`
(bone ID 44381/index 590) instead of rotating around the internal `PH_R_Hip`
joint. A newly spawned lantern is hidden and collision-free for a bounded
seven-sample calibration. Each physical-constraint quarter-turn is allowed 150
ms to settle, then the code reads:

- Rockstar's model bounds (`GET_MODEL_DIMENSIONS`) to obtain the geometry
  centre in model space;
- the live `Gun_GripR` world position; and
- that centre transformed through the attached entity.

The normalized `Gun_GripR -> geometry centre` vector is scored against world
down. The highest downward-scoring pose is selected, the prop is reattached once
at that measured pose, world collision is enabled, player-pair collision remains
disabled, and only then is it made visible. Every candidate vector/score and the
final selection are logged. The prior `+90 X` variant remains in the bounded set
only as `plus-x-runtime-rejected`; Lexer's visual disproof marks it ineligible to
win even if a noisy physical sample scored it highly. Failure to produce any
nonzero grip/centre vector removes the hidden prop and logs an error.

Death/swim/ragdoll native gates are now sampled with the existing 4 Hz health
cadence instead of every frame. When lit, entity validity/position plus the
frame-scoped light draw remain per frame so the light follows the physical prop.

### Lantern-only body transparency answer

No supported per-light entity exclusion mechanism was found, so none was
implemented. `_downloads/natives.json:23732-23772` resolves
`DRAW_LIGHT_WITH_RANGE` with only position, RGB, range and intensity. The
entity-light controls at `:23788-23842` expose only entity, color, intensity and
type. The object-light controls at `:53665-53723` expose intensity,
translucency and scattering; none accepts a ped/entity exclusion, shadow mask,
or "ignore this body" target. Searching the SDK/native list and Story scripts
found no `DRAW_LIGHT_*` shadow-exclusion partner or player-only light-occlusion
override. Making Arthur transparent to this lantern alone is therefore unknown/
unsupported through the resolved script-native surface. A second fake light on
the far side of his body was deliberately not substituted for that request.

Static verification passed with
`python tools/reverse-engineering/verify_belt_lantern_issue_5.py`. Runtime must
still confirm the selected calibration score corresponds to the visible body,
not merely its bounds, and that `CP_R_Belt` exists on both active protagonists.
No build, install, shared file, manifest, or GitHub state was changed.

## 2026-08-10 recurrence audit before holster/knife/leg clipping repair

- **Primary evidence/reference:** Lexer's latest live report says the lantern
  now faces correctly but continuously intersects the right gun holster, knife,
  and leg while walking. The previous bounds/down-vector calibration can prove
  orientation only; it cannot prove clearance from equipped accessories or an
  animated metaped surface. Required authority is the extracted player
  skeleton/bone map, vanilla weapon/accessory attachment data, current
  `belt_lantern.cpp`, the installed unified log, and opened Rockstar physical
  attachment call sites. A screenshot, bounds score, or attached heartbeat is
  not evidence of collision clearance.
- **Sanctioned path:** preserve the correctly facing pose and radial/stow
  behavior. Do not invent another axis, angle, or offset. A placement change is
  allowed only if a named exterior anchor or Rockstar accessory slot with
  demonstrated clearance is resolved from primary data. Physical attachment
  must remain one bounded constraint per spawn/owner transition; no per-frame
  reattachment or force-based separation is authorized.
- **Execution proof:** logs must distinguish resolved owner/prop bones, chosen
  constraint variant, one attachment call, attached/displacement readback,
  collision-pair policy, and bounded health heartbeat. Those prove execution,
  not visible non-intersection. Any proposed clearance mechanism must have its
  own authoritative readback or remain explicitly unproven.
- **Player-visible acceptance:** at rest and throughout walk, sprint, turn,
  crouch, mount/dismount, and stop, the correctly oriented lantern remains
  outside Arthur/John's body and does not pass through the right holster, knife,
  coat, or leg. It must still toggle exactly once through the radial and return
  the hand-held lantern to the belt. If a universal prop constraint cannot
  collide safely with animated player equipment, document that engine boundary
  rather than claim the clipping was fixed.
- **Every issue-owned per-frame native:** while lit, only the frame-scoped
  position read and `DRAW_LIGHT_WITH_RANGE` may remain per frame. Death/swim/
  ragdoll, bone/constraint health, displacement, selected weapon, spawn retry,
  and heartbeat stay at their existing bounded cadences. No collision toggle,
  attachment setter, task clear, pose mutation, or skeleton rebuild may run per
  frame.

## Evidence-backed clipping candidate: Rockstar's lantern holster anchor

The latest installed log proved the current candidate executed exactly as
authored: calibration selected `plus-y` at `CP_R_Belt`, remained attached, and
reported no displacement failure. Lexer's visible test nevertheless showed
continuous intersection with the right gun holster, knife, and leg. That
separates successful constraint/orientation execution from failed placement.

The Story weapon data resolves a more authoritative owner anchor than the
generic collision point. Every regular/Davy/electric lantern record uses
`HolsterAttachPoint=WEAPON_ATTACH_POINT_LANTERN`; the matching
`AttachPointInfos` entry in `datasets/vanilla/weapons.ymt:86871-86873` maps it
to `ID_PH_BELT_THROWER`. The extracted player skeleton resolves the runtime
bone name `PH_Belt_Thrower` as ID 2656/index 75. The module now resolves that
named vanilla lantern-holster bone for spawn, final constraint, health and
displacement checks. No rotation candidate, physical-constraint argument,
offset, radial/stow path, collision flag, or cadence changed.

This is a runtime candidate, not a non-clipping claim. Rockstar's attach-point
record deliberately hides weapons attached there, so the data proves intended
lantern ownership/placement but not that a forced-visible freely swinging prop
will clear every coat, holster, knife, and animated leg. Player-pair collision
remains suppressed because enabling collision between a ped and its own
physical constraint would risk pushing/jittering the player; the script surface
does not expose collision against individual metaped accessory meshes.

Static verification passed with
`python tools/reverse-engineering/verify_belt_lantern_issue_5.py`. Runtime must
confirm whether the vanilla anchor preserves the accepted downward pose while
clearing the equipped holster/knife/leg through the complete movement matrix.
If it still intersects, the evidence-backed conclusion is that a universal
script-attached prop cannot satisfy accessory-specific clearance without a
custom rigged metaped component; another guessed bone/offset is not authorized.
No build, install, shared file, workflow state, or label changed.
