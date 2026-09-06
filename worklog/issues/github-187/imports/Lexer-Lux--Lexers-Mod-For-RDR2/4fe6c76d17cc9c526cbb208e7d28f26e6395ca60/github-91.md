# GitHub #91 — autonomous owned-horse food and water

## Reference behavior and permissions

The closest behavioral reference was **Thirsty Horse** by alfabravozapa
([Nexus 2488](https://www.nexusmods.com/reddeadredemption2/mods/2488) /
[RDR2Mods 367](https://www.rdr2mods.com/downloads/rdr2/scripts/367-thirsty-horse/)).
Its published description said an unmounted horse
drank when left in shallow natural water or near a trough, ate near a haystack,
and grazed outside towns. Hay restored hunger faster than grass. Later versions
allowed a thirsty horse to approach nearby river water itself and made maximum
drinking depth configurable. **Horse's Needs** by bolmin70 was the older stated
inspiration ([Nexus 389](https://www.nexusmods.com/reddeadredemption2/mods/389))
and likewise triggered only when an unmounted horse was in water.
No source, binary, configuration, text, or asset from either mod was copied.
Nexus exposed no affirmative reuse permission, so they were used only as
behavioral references.

## Rockstar evidence

- `av_water_horse.c` selected
  `WORLD_ANIMAL_HORSE_DRINK_GROUND_DOMESTIC`.
- `animals_mammal.meta` defined
  `PROP_ANIMAL_HORSE_DRINK_TROUGH`,
  `WORLD_ANIMAL_HORSE_DRINK_GROUND_DOMESTIC`, and
  `WORLD_ANIMAL_HORSE_GRAZING_DOMESTIC` for the horse model set.
- `animals_mammal_ca.meta` proved the trough scenario used the authored
  `amb_creature_mammal@prop_horse_drink_trough` base/enter/exit clipsets and an
  environment `WATER_TROUGHS` prop. The grazing scenario used Rockstar's horse
  grazing conditional animation and chew VFX.
- `propsets.meta` identified `p_watertrough01x`, `p_watertrough02x`, and
  `p_watertroughsml01x` as `WATER_TROUGHS`, and `p_feedtrough01x` plus
  `p_feedtroughsml01x` as `FEED_TROUGHS`. Story scripts also referenced
  `P_WATERTROUGH03X`, `P_WATERTROUGH01X_NEW`, `P_HAYPILE01X/02X`, and low hay
  bales.
- Project policy in `codex/data-fundamentals.md` established horse Health Core
  as hunger and horse Stamina Core as thirst. The implementation wrote only
  `_SET_ATTRIBUTE_CORE_VALUE`, never attribute progression or the outer bars.

## Implementation

Added the isolated `modules/horse_needs.cpp` state machine and
`horse_need_sources.csv` model registry.

- It selected only `GET_OWNED_MOUNT`; no arbitrary horse pool was scanned.
- It required 15 seconds of stillness, a core at or below 75%, and the player
  to be 6–80 metres away. Mounted, attached/hitched, scenario-busy, fleeing,
  ragdoll, badly injured, combat, mission-locked, and recalled horses were
  rejected or interrupted.
- Trough drinking required an existing active Rockstar scenario point of the
  exact trough type within 4.5 metres of the detected trough. It never invented
  an alignment or teleported the horse.
- Hay selected one of eight level, dry, navmesh-safe points around an approved
  loose hay-pile or feed-trough model, required line of sight, and started the
  authored domestic grazing scenario without teleporting. Generic bale models
  were omitted because the same models occur in stacks, wagons, boats, and
  other decorative placements. Attached or moving source props were rejected;
  world props were never consumed or deleted.
- Core fill began only after the expected scenario type had actually run for
  four seconds, then advanced five points per second. Recall, mounting, danger,
  player approach, source unload, scenario exit, or timeout stopped the task
  cleanly. Falling and swimming horses were also rejected. Successful use
  imposed a five-minute cooldown.
- Natural-water drinking was deliberately deferred. The issue allowed this,
  the reference mods documented depth/clipping problems, and a safe shoreline
  solver requires runtime proof of reachable bank, depth, current/drop, and
  exact neck/head placement that static data cannot provide.

## Integration handoff

The integration agent must:

1. Include `modules/horse_needs.cpp` after the shared helpers/modules include
   block in `script.cpp`.
2. Call `updateAutonomousHorseNeeds(player, ped, now, locked)` once per live
   gameplay frame after `player`, `ped`, `now`, and the mission/menu `locked`
   flag are established.
3. Add the `[HorseNeeds]` INI section shown below and ensure
   `horse_need_sources.csv` is installed beside `GameplayTweaks.asi`:

```ini
[HorseNeeds]
Enabled=1
IdleSeconds=15
TriggerBelowCorePercent=75
MinimumPlayerDistance=6.0
MaximumPlayerDistance=80.0
ApproachTimeoutSeconds=20
MinimumUseSeconds=4
MaximumUseSeconds=24
RestoreIntervalMs=1000
RestorePointsPerTick=5
CooldownSeconds=300
DevelopmentTrace=0
```

## Static acceptance evidence and remaining runtime checks

Static inspection proved source identity, exact scenario hashes, owned-horse
scope, no teleport, no prop deletion, delayed gradual core writes, cooldown,
and interruption gates. Full compile/install belongs to the integration agent.
Lexer still needs to test multiple authored trough points and hay locations,
observe approach/alignment, verify gradual Stamina/Health Core fill, interrupt
with whistle/mount/combat, and confirm unrelated horses remain unaffected.

## Returned runtime test repair

Lexer reported that changing the settings still produced no horse action and
requested a horse-specific drink-source minimap icon for nearby drinkables
while actively leading the horse.

The installed `GameplayTweaks.log` from 2026-08-10 03:11 contained no
`[horse-needs]` line at all despite sustained live gameplay and heartbeats from
other modules. This did not prove that the update function failed to run: the
module had gated **every** line, including source load/start failure, behind
`DevelopmentTrace`. The failure therefore had no preserved rejection state.

Static inspection found two concrete blockers:

- The water path rejected every recognized trough without an already-active,
  separately pre-placed `PROP_ANIMAL_HORSE_DRINK_TROUGH` scenario point. The
  conditional animation itself declared prop id `TROUGH` with
  `UsePropFromEnvironment`; requiring a map-authored point was an unnecessary
  precondition and left ordinary streamed trough props inert.
- Test-oriented settings were silently constrained: `IdleSeconds=0` still
  waited five seconds, `CooldownSeconds=0` still imposed thirty seconds, and
  `MinimumPlayerDistance=0` still required two metres. The requested settings
  therefore were not the settings the state machine used.

The issue-local repair changed `modules/horse_needs.cpp` as follows:

- Existing active trough points remained preferred. If none existed, the
  module created a temporary `PROP_ANIMAL_HORSE_DRINK_TROUGH` point at the
  actual trough's exact world origin and heading, then associated the actual
  object with the conditional animation's declared `TROUGH` prop id. It tracked
  ownership and deleted only that temporary point at every stop/failure path.
  No prop offset, horse teleport, or object deletion was introduced.
- Zero idle/cooldown/minimum-distance settings became real zeroes. Production
  defaults remained 15 seconds, five minutes, and six metres.
- INFO/WARN/ERROR lifecycle lines became always-on. A five-second bounded
  heartbeat now distinguished no owned horse, disabled, busy/interrupted,
  player-distance, idle wait, approach/use, and source-scan outcomes and
  retained the latest start rejection. Restoration tick detail remained under
  `DevelopmentTrace`.
- Exact native state (`PED::_IS_PED_LEADING_HORSE` plus
  `PED::_GET_LED_HORSE_FROM_PED`) gated a 2 Hz scan for configured, streamed
  horse-water sources within 100 metres. Only when the player was actively
  leading the owned horse did those sources receive the custom
  `LEX_BLIP_HORSE_DRINK` coordinate blip; every marker was removed when leading
  stopped. Leading also interrupted/rejected autonomous horse control.
- Added an original 32x32 RGBA source asset at
  `icons/horse-needs/horse-drink-source.png`: a horse lowering its head into a
  trough, so the marker cannot be mistaken for player-drinkable water.

`tools/reverse-engineering/verify_horse_needs_issue_91.py` passed. It checked
the scenario create/associate/delete lifecycle, exact `TROUGH` prop binding,
exact leading-horse identity, 100 m / 2 Hz icon layer, marker teardown,
zero-valued test settings, always-on heartbeat, delayed restoration, owned
horse scope, absence of teleports/object deletion/arbitrary pools, source rows,
and the icon's 32x32 dimensions plus real alpha. `py_compile` and
`git diff --check` also passed.

Integration still needs to add the source icon to `lex_blips.ytd` under texture
name `LEX_BLIP_HORSE_DRINK`, then compile/install/hash-verify the combined build.
Runtime acceptance remains open: confirm the horse enters the trough clip with
correct pose/alignment, gradual Stamina Core restoration begins only after the
clip runs four seconds, the icon appears only while leading within roughly
100 metres, and the new heartbeat names the actual gate if the task still does
not start.

## Returned-test clarification and diagnostic contract

The later live comment clarified that repeated head-lowering and occasional
pawing/digging were observed, but might have been ordinary vanilla idle motion.
Those motions were not accepted as evidence that this module ran.

The diagnostics were tightened so the next single run answers that ambiguity:

- `config-applied hot-reload<=2s` printed every effective INI value whenever it
  changed. HorseNeeds INI values were polled every two seconds and did **not**
  require restarting the game. This also exposed any clamping immediately.
- `scenario-issued call-only` meant only that the module attempted its task
  native. It was deliberately not described as successful behavior.
- `mod-scenario-confirmed` appeared only after the horse's active scenario type
  read back as the exact scenario the module issued. The heartbeat also included
  `using-scenario`, `active-scenario`, `expected-scenario`, point handle, and
  point user. Vanilla head dips/pawing with no matching state therefore remained
  `mod-scenario-confirmed=0`.
- Visual pose/alignment still required Lexer to look at the horse. The confirmed
  scenario line explicitly reported `visual-acceptance=pending`; it did not
  claim that a native readback proved a good-looking pose.

Added `ini-fragments/github-91.ini` as the issue-owned integration/help source.
It documented that INI values hot-reloaded within two seconds, while the source
CSV (loaded once per ASI session) and newly installed streamed icon texture
required a game restart. The fragment preserved Lexer's easier returned-test
profile (2-second idle, 99% trigger, 1 m minimum distance, 5-second cooldown)
so integration would not silently restore the production defaults before the
next acceptance run.

The live request explicitly named water barrels as well as troughs.
`common_0_data/fluidvessels.meta` resolved `p_barrelwater01x` to
`VFXLIQUID_TYPE_WATER`, so `P_BARRELWATER01X` was added to the water registry.
It received the same 100 m, exact-owned-led-horse icon gating and explicit
`TROUGH` prop-slot binding. Unlike the three models in Rockstar's
`WATER_TROUGHS` prop set, the barrel remained pose-sensitive; the registry
comment and acceptance boundary retained that fact rather than claiming static
proof of good horse/barrel alignment.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
## fuckups.txt recurrence audit

- Easier INI values and ordinary horse head-lowering were previously treated as evidence even though the installed code silently re-clamped the settings, rejected troughs without a pre-existing scenario point, and logged nothing outside DevelopmentTrace.
- The next candidate must be checked against the actual reference mod before any further animation/scenario guess is shipped. Its diagnostics must distinguish call intent from confirmed scenario ownership, and the lead-only blips must be visible in the packed live dictionary—not merely declared in source.

## 2026-08-10 returned-test root cause and reference-binary audit

This pass began from the failed runtime evidence, before changing source. The
installed `D7BCACD0...476C` log did not show a rejected trough, a failed scenario
point, or an animation failure. It reported `horse=0` and
`gate=no_owned_horse` for the entire session. Consequently neither autonomous
needs nor the lead-only blip scan could execute. The module used only
`PLAYER::GET_MOUNT_OWNED_BY_PLAYER`; that native returned zero for Lexer's
current Story saddle horse in the actual failed session. Treating that single
getter as the authoritative current horse was the immediate shipped defect.

The exact Thirsty Horse 1.6 archive was then retrieved and hash-checked against
the Nexus-published VirusTotal SHA-256. Both are
`65EE0D0251F722FE8AF84E645F6613B5C03AAA7B99A6D8F736830F16865D725D`.
Direct PE disassembly, rather than the mod-page description, established its
trough contract:

- It scans the real `p_watertrough01x`, `p_watertrough02x`,
  `p_watertrough01x_new`, and `p_watertrough03x` objects.
- It moves the horse with `TASK_GO_STRAIGHT_TO_COORD`, aligns it with
  `TASK_ACHIEVE_HEADING`, clears the approach task, and plays the authored
  `AMB_CREATURE_MAMMAL@PROP_HORSE_DRINK_TROUGH@STAND_ENTER` / `ENTER` pair,
  transitioning against the corresponding `...@BASE` / `BASE` state.
- It does not create a `PROP_ANIMAL_HORSE_DRINK_TROUGH` scenario point or bind a
  runtime prop to one. The prior temporary-scenario implementation therefore
  was not a port of the cited reference; it was another unproven guess.
- The reference contains manually authored trough locations/approach headings,
  so it does not prove that placing the clip at an arbitrary object's origin is
  geometrically valid. Generic trough/barrel alignment must remain bounded and
  visually pending rather than being described as source-proven.

The source repair must first resolve the actual current owned/saddle horse using
Rockstar's dedicated active/saddle getters (with current mount and exact led
horse as direct evidence), then adopt the reference's explicit approach,
heading, and animation-state contract. It must never restore a core from task
intent alone. The next installed log must name every candidate horse getter and
the selected source so another `horse=0` session cannot be misreported as an
animation failure.
