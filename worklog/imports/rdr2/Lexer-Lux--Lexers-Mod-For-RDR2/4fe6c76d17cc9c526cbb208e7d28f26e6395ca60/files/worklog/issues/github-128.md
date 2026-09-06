# GitHub #128 - Two Camera Modes

## Requested behavior

Lexer, verbatim: "the whole 'two camera modes' thing? works great....except on
horseback, where there's no change at all from vanilla. back to 4 modes there
(3 third-person zoom levels + First person)".

So: the two-mode view cycle already works on foot. It must also apply on
horseback, where the stock four-view cycle is still active.

## Cause

Not a native or engine problem. It was an explicit exclusion shipped with #8.

`GameplayTweaks/modules/gameplay_camera.cpp` gated the zoom lock to the three
on-foot stances:

    if (g_gameplayCameraLockZoom &&
        (mode == GameplayCameraMode::Standing ||
         mode == GameplayCameraMode::Crouched ||
         mode == GameplayCameraMode::Prone))
        invoke<Void>(0x718C6ECF5E8CBDD4);

`worklog/issues/github-8.md` states the decision outright: "The existing on-foot
zoom-lock option is retained only for standing, crouched and prone modes. It is
not forced onto aim, horseback, or vehicle cameras."

Mounted therefore fell through to Rockstar's own view cycling - exactly the
"no change at all from vanilla" that was reported. The rest of the module did
run mounted (the Horseback profile's shoulder offset and distance are applied
through `_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE`), which is why only the *mode
count* was wrong and nothing else.

## Native audit

Three per-frame third-person framing natives exist, all declared in the local
SDK header and named in the local native database. Nothing here is inferred:

| hash | natives.h | natives.json | name |
| --- | --- | --- | --- |
| `0x718C6ECF5E8CBDD4` | :717 | :9147 | `_FORCE_THIRD_PERSON_CLOSE_THIS_FRAME` |
| `0x8370D34BD2E60B73` | :718 | :9154 | `_FORCE_THIRD_PERSON_CAM_THIS_FRAME` |
| `0x1CFB749AD4317BDE` | :719 | :9161 | `_FORCE_THIRD_PERSON_CAM_FAR_THIS_FRAME` |

natives.json comments: "Forces camera position to closest 3rd person" /
"second furthest 3rd person" / "furthest 3rd person".

There is no view-mode *setter* and no override-slot global for this the way
`Global_1911667` exists for the radar. A full scan of the local native database
for "view mode", "camera mode", "zoom level", "third person", "first person",
"mount cam" and "horse cam" returns only the natives above plus
`_IS_IN_FULL_FIRST_PERSON_MODE`, `_FORCE_FIRST_PERSON_CAM_THIS_FRAME`,
`_0x632BE8D84846FA56`, `_0x71D71E08A7ED5BD7` and
`_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE`. The per-frame force *is* Rockstar's own
mechanism for this, not a workaround around one: 12 shipped call sites use
`0x718C6ECF5E8CBDD4` this way.

### Evidence the framing natives are not on-foot-gated

None of these natives is named or documented as on-foot only (contrast
`_DISABLE_ON_FOOT_FIRST_PERSON_VIEW_THIS_UPDATE_2`, natives.json:9176, which is).
Shipped call sites issue them on a tick where the script has already branched on
the player being mounted:

- `beat_murder_campfire.c:3243` takes `PED::GET_MOUNT(Global_35)`, branches on
  the mounted case at `:3250-3252`, and calls the framing native at `:3259` and
  `:3266` on both the mounted and dismounted paths.
- `braithwaites3.c:34950` enters `if (PED::IS_PED_ON_MOUNT(Global_35))`, and
  `:34964` calls `CAM::_0x8370D34BD2E60B73()` in the same function body.
- `mudtown3b.c:57841` calls `CAM::_0x718C6ECF5E8CBDD4()` gated on `func_2116`,
  whose body is a `PED::IS_PED_ON_SPECIFIC_VEHICLE` test - i.e. specifically
  when the player is riding something.

## Implementation

`GameplayTweaks/modules/gameplay_camera.cpp`:

- Added `gameplayCameraForceThirdPersonLevel(int)` wrapping the three verified
  hashes above in the order the view key cycles them.
- The on-foot lock now calls that helper with level 0 instead of invoking the
  hash inline. Behaviour is byte-identical to before; on-foot is untouched.
- Added a mounted branch: when `LockToOneThirdPersonZoomMounted` is on and the
  active mode is `Horseback`, the configured step is forced every frame.
- `gameplayCameraMode(ped)` is now computed once per update instead of twice.

Which step to pin is configurable rather than hard-coded to "closest" because
the mounted follow rig sits further from the player than the on-foot one, so
"closest" mounted is not visually the same framing as "closest" on foot. The
default is 0, matching the on-foot behaviour that was reported as working.

Aim still takes precedence over Horseback in `gameplayCameraMode()`, so mounted
aiming keeps the shared aim profile exactly as it does on foot.

Vehicle mode was left alone. The report names horseback only, and a wagon seat
is a different rig again; extending the lock there without a request would be
guessing.

## New INI keys (`[Camera]`)

    LockToOneThirdPersonZoomMounted=1   ; 1 = two-mode lock on horseback too
    MountedThirdPersonLevel=0           ; 0 closest, 1 middle, 2 far

Setting `LockToOneThirdPersonZoomMounted=0` restores the previous, pre-#128
mounted behaviour without touching the on-foot lock.

## Not done / open

- Not compiled, linked, installed or copied. Static change only, per the task
  constraints.
- In-game acceptance is required and is the only way to settle one thing:
  whether pinned level 0 is the right default framing for the mounted rig, or
  whether level 1 reads closer to the on-foot result. That is a one-line INI
  change, no rebuild.
- No new module file was created; no `script.cpp`, `build.bat` or other module
  was touched. `horse_camera.cpp` is unrelated to this issue (it is the #47
  auto-centering module and is deliberately inert) and was not modified.
- No labels changed, no commits, no pushes.

## Integration verification

`python tools/reverse-engineering/verify_two_camera_modes_issue_128.py` checked
all three named third-person framing hashes, the mounted-only force branch, aim
precedence, both INI keys, and the explicit exclusion of vehicles. Combined
build/install and in-game confirmation remain pending.

The combined release compiled successfully as ASI SHA-256
`AEAE1D1D1C53861A6F507815030957D333E77D097E9F2E7F899EF5B2FF82B2A3`.
RDR2 was running, so installation remained pending.

## `fuckups.txt` recurrence audit

- This issue uses three frame-scoped camera natives, so the per-frame mutation
  rule applies. Their local names explicitly end in `_THIS_FRAME`, which
  supports the required cadence; no persistent camera setter has been resolved.
- The earlier worklog overstated two call sites. `beat_murder_campfire.c:3259`
  calls `0x632BE8D84846FA56`, not one of these three framing natives.
  `braithwaites3.c:34950` checks mount state, but the later
  `_0x8370D34BD2E60B73` call at :34965 is gated by a separate anim-scene
  condition, not by that mount branch. Those are not evidence for mounted use.
- `mudtown3b.c:57839-57842` does call the close-camera native from a predicate
  whose definition at :74215-74242 proves a specific **vehicle**, not a horse.
  It proves the native is not on-foot-only, but does not prove the desired horse
  result.
- The implementation therefore remains an evidence-backed candidate, not an
  accepted horse mechanism. Runtime acceptance must show that horseback view
  cycling is actually reduced to first/one third-person mode while aim and
  vehicles retain their stated behavior. A build, call, or log line cannot
  settle that visual postcondition.

## Independent pre-build audit

The runtime branch itself was not changed. It is safe to include only as a
runtime candidate: all three invoked hashes resolve in `_downloads/natives.json`
to frame-scoped third-person positions, and their `_THIS_FRAME` contract makes
the horseback-only per-frame cadence intentional rather than an accidental
persistent engine fight. `_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` and the
LOW/NORMAL control used by #8 are independently documented as per-update/
per-frame interpolation controls; #128 neither adds another orbit writer nor
changes those calls.

One concrete evidence defect remained after the recurrence audit: the source
comment still repeated the invalid `beat_murder_campfire`, `braithwaites3` and
`mudtown3b` horse claims. The first invokes `0x632BE8D84846FA56`, the second's
camera force is gated by a separate anim-scene predicate, and the third proves
a specific vehicle only. The comment was replaced with the accurate boundary:
no opened Story call site proves horse support. The verifier now reads the
actual native database, rejects those three citations if they return, and says
"runtime candidate" instead of claiming the mounted cycle is already pinned.

No conflict with #8 was found. `gameplayCameraMode()` still gives Aim precedence
over Horseback; the new force is restricted to Horseback; Vehicle remains
excluded; and the accepted on-foot branch still pins level 0 exactly as before.
The mounted level clamp remains 0..2, matching the three documented framing
natives.

The unresolved acceptance boundary is entirely player-visible: while mounted
and not aiming, repeated view-key presses must alternate only between first
person and the configured single third-person framing, without jumping or
oscillation from the concurrent #8 mounted distance/shoulder profile. Mounted
aim must retain the #8 Aim profile, dismounting must restore the accepted
on-foot two-mode behavior, and wagons/vehicles must retain their stock view
cycle. A successful build, verifier, or native-call log cannot establish any
of these postconditions.

## 2026-08-10 returned vehicle/first-person correction

The latest result explicitly extends the requested two-mode behavior to
vehicles and reports that the current build removed vehicle first person. The
source exposed why: `gameplayCameraFirstPerson()` used unresolved native
`0xA24C1D341C6E0D53(1,0,0)` as its ordinary first-person guard even though the
local native database names the zero-argument `0xD1BA66940E94C547` as
`_IS_IN_FULL_FIRST_PERSON_MODE` with the contract "Returns true if player is in
first person." The wrong guard could stay false in the vehicle first-person rig,
allowing this module's third-person profile write to pull the view back out.

The guard now uses the named zero-argument predicate plus Rockstar's separate
first-person-aim predicate. It runs before every profile/framing mutation.
Vehicle joins Horseback in the configured two-mode branch, so both rigs retain
first person and collapse only their three third-person steps to the configured
single step. The existing mounted setting is relabelled/documented as mounted
and vehicle behavior rather than adding a second drift-prone control.

The #128, #8 and #154 camera verifiers passed together. Installed in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`; horse/vehicle first-person retention and two-mode cycling remain `test me`.

## 2026-08-10 returned vehicle-input audit

Lexer pressed the normal view key in a vehicle and nothing changed. The module
was forcing its selected third-person level on every vehicle frame. Its
first-person guard could run only after Rockstar had entered first person, but
the same-frame force prevented that transition from completing.

The correction must let Rockstar own the view-key transition. A rising edge of
the named `INPUT_NEXT_CAMERA` action starts a bounded 500 ms handoff in which no
third-person framing native runs. If Rockstar enters first person, the existing
first-person guard keeps all profile writes off. If it remains in third person,
the configured single third-person level resumes after the handoff. The edge and
result are logged; an input read alone is not visible acceptance.
