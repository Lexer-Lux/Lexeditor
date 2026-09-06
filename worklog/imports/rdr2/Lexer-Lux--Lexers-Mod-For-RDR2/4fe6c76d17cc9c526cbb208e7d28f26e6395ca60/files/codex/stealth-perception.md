# Stealth and perception

### Settled result

RDR2 does not expose one complete "stealth calculation." It layers engine
perception, `pedperception.meta`, audible-event tuning, mission-script
overrides, line of sight, witness/crime logic, and AI state. Crouch and
`SET_PED_STEALTH_MOVEMENT` are separate states. Prone must therefore apply its
own explicit perception policy; copying the crouch flag is not a complete
stealth implementation.

### Confirmed editable inputs

### `common:/data/pedperception.meta`

Each named perception profile owns:

- minimum/maximum central and peripheral seeing ranges;
- hearing range and, for animals, wind/no-wind smell ranges;
- identification range;
- horizontal/elevation field of view and centre-of-gaze angle;
- movement-detection time;
- close/far standing and crouched velocity thresholds;
- a time-of-day/weather modifier profile.

Vanilla human defaults are 60 m central sight, 5 m peripheral sight, 60 m
hearing, 20 m identification, a horizontal field from -90 to +90 degrees, and
200 ms movement detection. `DEFAULT_LAW_PERCEPTION` uses the law time-of-day
profile. `PINKERTON_PERCEPTION` differs by using 60 m identification.

`TOD_MOD_PED` and `TOD_MOD_LAW` reduce seeing range to 0.5 at 23:00-04:59,
0.75 at 05:00 and 22:00, and 1.0 at 06:00-21:59. This proves darkness is
represented globally by time-of-day range multipliers. It does not prove
per-light or per-shadow illumination sampling.

The generic default modifier also contains independent rain, fog, snow,
sandstorm, and wind modifiers for sight and hearing. Negative-one entries in
the PED/LAW weather tables are inheritance/sentinel values; they must not be
presented as literal negative perception ranges.

### `common:/data/ai/noisetuning.meta`

Footsteps are five event tiers with vanilla SP min/max distances:
`0/0`, `2.25/36`, `2.5/40`, `5/80`, and `10/160` metres.
Foliage applies a `0.1` sound factor and horse footsteps a `2.0` hardness
multiplier. The file exposes global event propagation, not a direct
player-crouch noise multiplier.

### Runtime per-ped natives

Decompiled Story scripts confirm mission/runtime overrides for:

- seeing range;
- hearing range;
- identification range;
- visual-field min/max angle, centre angle, and peripheral range;
- visibility tracking (`REQUEST_PED_VISIBILITY_TRACKING` and
  `IS_TRACKED_PED_VISIBLE`);
- Rockstar stealth movement and crouch movement as separate states.

These setters are authoritative per-ped overrides, but public natives expose
no getter for the original effective seeing/hearing values. A runtime modifier
must cache what it applies and restore a chosen baseline; it cannot safely
discover and preserve arbitrary mission overrides after overwriting them.

### Engine/script-owned inputs

| Input | Finding | Ownership |
|---|---|---|
| Stance | Crouch has dedicated velocity thresholds; stealth movement is a separate native state. | Engine + data |
| Movement speed | Standing/crouched close/far velocity thresholds are data. Story helpers also use short qualification timers. | Data + engine + scripts |
| Noise | Footstep tiers, foliage factor, and horse multiplier are data. Which tier an animation/material emits is engine/audio-event logic. | Data + engine |
| Cover/occlusion | Scripts use engine visibility tracking and LOS checks. No global cover stealth multiplier was found. | Engine + scripts |
| Darkness/weather | Hourly sight and weather sight/hearing modifiers are data. Local shadow/light exposure was not found. | Data; local lighting unproven |
| Vegetation | Foliage audibility factor is data. No visual concealment multiplier was found. | Audio data; visual concealment unproven |
| Clothing | No perception field or Story-script calculation tying clothing to visibility was found. | Unproven |
| Weapon/light sources | No general illumination multiplier was found. A common Story visual helper has an explicit close-range lantern/torch fallback at night. | Scripts; local illumination multiplier unproven |
| Witness awareness | Crime witness information, confrontation/report delays, immediate-detection ranges, and mission conditions are a layer after perception. | Crime data + scripts |
| AI state | Suspicious/investigating/combat transitions are decision/event logic; missions frequently force ranges or state. | Engine + scripts/programs |
| "Stealth mode" | Scripts set/query it independently of crouch and sometimes branch on it, but no public scalar definition or extracted formula exists. | Engine-owned flag/state |

Absence above means "not found in the complete extracted data and decompiled
Story-script surfaces inspected," not proof that compiled engine code lacks
the behavior.

### Detection and awareness model

There is no single universal detection meter.

- **Sensory detection** is mostly qualification plus a short time gate:
  distance, FOV, LOS, hearing events, movement speed, stance thresholds, and
  the profile's `MovementDetectionTime` (vanilla profiles use 200 ms). Story
  scripts query perception/visibility and frequently transition directly when
  the result becomes true. No editable accumulating visual-detection score or
  decay rate was found.
- **Witness suspicion** is a real normalized accumulating value. Interaction
  rules add amounts such as 0.11, 0.15, 0.21, 0.25, 0.5, and 0.55; suspicion
  decays; conditions compare it against thresholds (for example 0.35 can start
  an aggressive confrontation). Separate states confirm or forgive crimes.
  The public `_GET_PED_MOTIVATION` native can read this value for a target ped.
- **Combat** is not simply the top of the suspicion meter. Damage, hostility,
  weapons, crimes, relationship groups, scripted conditions, anger/fear
  motivations, and threat events can enter combat or flee states directly.
  Witness rules separately use anger 0.95 for a fight transition.
- **Animals** use detected-threat events and discrete unalerted, alerted,
  threaten, flee, and attack tasks. `animaltasks.meta` supplies many transition
  delays and evasion timings; this is separate from human witness suspicion.

Therefore RDR2 is a hybrid. Witness handling resembles an accumulating
threshold/decay system. Ordinary enemy sight is closer to a conditional,
time-gated event/state machine. Animals use their own event/task state machine.
An MGSV-style universal numeric indicator would have to be a mod-owned estimate,
not a readout of one Rockstar detection value.

### Common Story hostile-detection helper

The decompiled Story scripts repeat a standard detection-helper family. The
following configured instance is `gang1.c`, `func_1745`, `func_2180`, and
`func_2181`. It is authored script logic, not one universal engine rule, but
the same lantern branch occurs in 110 extracted Story scripts and the same
noise-threshold branch occurs in 100.

- Immediate visual detection in `func_2459` uses a configured base distance of
  30 m and rejects targets beyond 35 m. Inside that gate, it caps the ped's raw
  seen-range value at 35 m, requires
  `IS_TARGET_PED_IN_PERCEPTION_AREA`, and requires
  `CAN_PED_SEE_ENTITY(...) == 1`. This is a conditional result, not a filling
  visibility bar.
- The same branch has a lantern/torch fallback. It applies at 5 m or less,
  during the helper's night window of 20:20 through 05:20, when the player is
  facing the observer within 110 degrees and the observer has clear LOS.
- Noise detection in `func_2460` requires
  `GET_PLAYER_CURRENT_STEALTH_NOISE > 4` and a second unresolved native that
  takes the player, observer, and a stance-dependent flag. Crouch or cover sets
  that flag to zero. With the configured suppression flag, cover blocks the
  result and crouch can block it. A separate stealth-state branch tests noise
  above 8. The unresolved native prevents a complete hearing-distance formula
  from being stated.
- The timed visual branch in `func_2462` uses a configured 15 m range and a
  1000 ms continuous qualification timer. At less than 3.5 m it can complete
  after 500 ms. If qualification stops, the helper does not expose a universal
  fractional awareness value for an indicator.

Thus stance and speed matter through at least two paths: perception-profile
movement thresholds and the engine stealth-noise scalar. In the controlled
runs, crouch-walk noise was 0, standing walk was about 1.83, run was 5, and
sprint was 10. The common Story noise branch's first scalar threshold is above
4, so run and sprint can qualify while those tested walk states do not. The
unknown native, distance, AI profile, cover, and script flags still decide
whether that qualified noise becomes detection.

### Controlled free-roam observer results

The self-verifying `StealthProbe` completed two runs with a rendered,
human, neutral observer on open ground. These results describe the probed
natives and this ambient observer; they are not a substitute for authored
mission or enemy AI.

- `IS_TARGET_PED_IN_PERCEPTION_AREA` was the useful geometric qualification.
  At 15 m it was true from 0 through 55 degrees off-centre and false at 60,
  85, 95 and 120 degrees. It was true at 5, 15, 30, 45 and 60 m head-on and
  false at 75 m. Setting the observer's seeing range to 5 m made it false at
  15 m; restoring 60 m made it true again. The tested native call therefore
  has an observed horizontal boundary between 55 and 60 degrees and a range
  boundary between 60 and 75 m in this setup. That boundary must not be
  presented as the complete profile FOV or a universal detection cone.
- The perception-area result followed even 150 ms facing pulses. It did not
  accumulate or decay: it became false again when the observer faced away.
- `CAN_PED_SEE_ENTITY` remained true with the observer facing 180 degrees away,
  so it is not a complete FOV/detection result. It dropped outside/at the sight
  range and under a 5 m seeing-range override. `CAN_PED_SEE_PED_CACHED` often
  stayed true across those changes and is not suitable as an immediate
  detection signal.
- The open-ground run did not test actual foliage or cover. The foliage-check
  form of `CAN_PED_SEE_ENTITY` matched the non-foliage form throughout the
  valid near-range samples, so visual vegetation concealment remains unproven.
- All enabled suspicion, fear, anger and agitation motivation reads remained
  `0.000` for the neutral observer. These values cannot be treated as a
  universal ambient awareness meter in that setup. The synthetic-hostility
  null result is invalid as detection evidence because the observer remained
  under an indefinite `TASK_STAND_STILL`, suppressing autonomous AI response.
- Crouch and stealth movement were empirically separate: crouch was active
  while the stealth-movement flag remained false. After instruction-transition
  trimming, crouch-walking at median 1.365 m/s produced exactly `0.000` player
  stealth noise. Standing walking at median 1.333 m/s produced median `1.827`
  noise; running produced median `5.000`; sprinting produced median `10.000`.
  This confirms that stance and locomotion affect the engine's player-noise
  scalar, but not how a particular material or AI profile consumes it.
- Merely drawing a weapon caused no observer reaction. Aiming at the neutral
  observer caused fleeing about 526 ms after the aiming flag became active,
  without changing the logged motivation values or witness state. Holstering
  cleared the fleeing state. Threat reaction is therefore a separate event/AI
  path, not the top of the motivation readings sampled here.

The completed runs did not establish actual hostile notice, investigation or
combat timing; accumulation versus reset; effective hostile sight distance;
or the effects of stance, movement noise, time/weather, solid cover and carried
light on those transitions. Actual foliage, local shadow, surface material,
animals, law and scripted hostiles are also untested. Their data/script findings
elsewhere in this audit remain the limit of what is confirmed.

### Installed prone reference

The installed `Dive - Crawl N' Gun.asi` is closed binary reference material.
Its INI independently exposes `StealthModeEnabled`, prone input, and stealth
input. That corroborates the native/script finding that prone animation,
crouch, and stealth mode are distinct. It does not prove an internal
perception formula and its binary is not a source-code base for our release.

### Crouch/prone design

1. Preserve Rockstar crouch and stealth states. Tapping crouch continues to use
   the game's crouch/stealth transition; holding it enters our prone state.
2. Do not globally rewrite NPC perception every frame. Mission scripts use the
   same setters, and blind overwrites would break authored encounters.
3. Use data for durable world rules:
   - tune named human/animal perception profiles in `pedperception.meta`;
   - tune global audible-footstep propagation in `noisetuning.meta`.
4. Prone should supply benefits crouch does not automatically prove:
   - lower locomotion speed/noise through prone animation/event selection;
   - lower exposed silhouette through the actual pose and normal LOS;
   - optional explicit runtime sight/hearing modifiers only for ambient hostile
     peds, excluding mission/scripted peds and witnesses already reporting.
5. A safe first implementation should leave per-ped ranges untouched and test
   whether pose, speed, native stealth mode, vanilla LOS, and the existing
   crouched velocity thresholds already produce the desired result.
6. If extra runtime scaling is needed, make crouch/prone sight and hearing
   multipliers hot-reloadable, cache every ped/value we set, restore on stance
   exit/despawn, and never claim mission compatibility until tested.
7. Stealth indicators (TODO 111) should read target awareness state, visibility,
   distance, and LOS. They must not infer awareness from distance alone.

### LEXEDITOR ownership

Perception profiles are shared types, not one record per individual ped model.
Persistent data does not provide a complete `model -> perception profile`
mapping in this extract. Runtime per-ped setters affect spawned instances and
must not be mislabeled as persistent per-model data.

The AI tab currently exposes:

- global audible-event tuning from `ai/noisetuning.meta`;
- named shared human/animal perception profiles from `pedperception.meta`;
- combat profiles separately from perception.

The editor starts from the vanilla extract when the mod has no local
`pedperception.meta`. The first saved perception edit creates the mod file and
adds the correct LML replacement. This keeps LEXEDITOR usable without enabling
MyOverhaul and avoids silently activating a vanilla-identical replacement.

The intended semantic layout is:

1. **Perception:** Human profiles, Animal profiles, and Environment modifiers.
2. **Awareness:** Human motivations/witness thresholds and Animal threat/task
   timings, kept separate because they are different state machines.
3. **Noise:** global footstep, foliage, and horse audibility.
4. **Combat:** existing combat profiles/programs.

The LEXEDITOR Mobs tab satisfies this rule and must keep satisfying it: it is
record-oriented, one row per profile or archetype, never one row per ped model.
Do not add a model-oriented view until a reliable model -> profile/archetype
binding is extracted, and when it is, link to the shared profile rather than
duplicating its values per model.

### Evidence inspected

- `_downloads/extract/common_0_data/pedperception.meta`
- `_downloads/extract/common_0_data/ai/noisetuning.meta`
- `_downloads/RDR2-Decompiled-Scripts/script_rel/`
- `_downloads/RDR2_SDK/SDK/inc/natives.h`
- installed `Dive - Crawl N' Gun.ini` and binary metadata
- completed controlled-observer logs
  `StealthProbe-20260728-055229.csv` and
  `StealthProbe-20260806-061137.csv`

