# GitHub #89 — drink/refill at water pumps

## Requested result

At an eligible `p_waterpump01x`, show hold-E Drink and hold-R Refill Canteen.
Both must use Rockstar's complete pump scenario so the player aligns and the
handle moves. Drink restores exactly #88's configured Stamina Core amount;
refill fills #88's reusable canteen without changing the core.

## Rockstar evidence

- `propscenarios.meta` attaches `PROP_HUMAN_PUMP_WATER` to every
  `p_waterpump01x` at authored local offset `(-0.049, 0.819, 1.0)` and heading
  pi. This existing active scenario point is a reliable per-prop source for the
  exact interaction transform.
- `mech.meta` defines `WORLD_PLAYER_CHORES_PUMP_WATER` with weapon/gesture
  blocking, kinematic ped physics, enter alignment, exit direction, pickup-prop
  handling, a spawned bucket, and both player conditional variants.
- `mech_ca.meta` proves `PROP_HUMAN_PUMP_WATER_PLAYER` and
  `PROP_HUMAN_PUMP_WATER_BUCKET_PLAYER` use the actual scenario pump through
  `p_waterpump01x_PH_L_HAND` plus the authored player base/enter/exit clipsets.
  The bucket variant carries its own scenario-prop requirements.
- Rockstar's camp scripts monitor the player's exact active scenario, disable
  control while pump-water starts, and request the native scenario exit with
  `0xFDECCA06E8B81346`; they do not approximate the chore with `TASK_PLAY_ANIM`.
- Shipped animation-event strings include
  `ENT_ANIM_PED_WATER_DRINK_PUMP`, `ENT_ANIM_WATER_BUCKET_FILL`, and
  `ENT_ANIM_BUCKET_FILL_SPLASH`.

Primary local evidence:

- `_downloads/extract/update_1_common/common/data/ai/propscenarios.meta`
- `_downloads/extract/update_1_common/common/data/ai/scenarios/mech.meta`
- `_downloads/extract/update_1_common/common/data/ai/scenarios/conditionalanims/mech_ca.meta`
- `_downloads/RDR2-Decompiled-Scripts/script_rel/camp_horseshoeoverlook.c`
- `_downloads/RDR2-Unhashed-Strings/DataLines.txt`

## Isolated implementation

Added `GameplayTweaks/modules/water_pumps.cpp` (unregistered). It:

1. scans only for the exact pump model and its nearby active authored
   `PROP_HUMAN_PUMP_WATER` point;
2. rejects occupied, invisible, obstructed, distant, mission, combat, ragdoll,
   airborne, mounted, dead, locked, or already-in-scenario states;
3. shows native hold prompts on `INPUT_CONTEXT_X` (E) and `INPUT_RELOAD` (R),
   with disabled `No Canteen` / `Canteen Full` refill states;
4. creates `WORLD_PLAYER_CHORES_PUMP_WATER` at the existing authored point's
   exact coordinates and heading, associates the actual pump object as
   `p_waterpump01x_PH_L_HAND`, and tasks the player onto the appropriate exact
   conditional variant;
5. grants no reward on task issuance or an elapsed-time guess: Drink waits for
   `ENT_ANIM_PED_WATER_DRINK_PUMP`; Refill waits for Rockstar's bucket-fill
   event;
6. updates CoreClock's managed Stamina Core alongside direct Drink restoration;
7. requests Rockstar's authored scenario exit after the event and defers point
   deletion until the ped has left; and
8. exits without reward on interruption, approach timeout, missing event, or
   premature scenario termination.

There is deliberately no loose animation, static handle, teleport alignment,
or `TASK_START_SCENARIO_AT_POSITION` fallback.

## Narrow #88 API boundary

The pump module knows no #88 globals, inventory representation, persistence
file, or capacity constant. Integration supplies only:

```cpp
struct WaterPumpCanteenApi {
    bool (*owned)();
    int (*charges)();
    int (*capacity)();
    bool (*refillToCapacity)();
    int (*staminaCorePerDrink)();
};
```

#88 already exposes the latter four operations as
`reusableCanteenCharges`, `reusableCanteenCapacity`,
`refillReusableCanteen`, and `reusableCanteenStaminaCorePerDrink`. The
integration agent should add this equally narrow ownership accessor inside
`reusable_canteen.cpp`:

```cpp
static bool reusableCanteenOwned() {
    loadReusableCanteenState();
    return g_reusableCanteen.owned &&
        INVENTORY_ITEM_COUNT(joaat("LEX_WATER_BOTTLE")) > 0;
}
```

Then, after both module includes and before the main loop, register once:

```cpp
configureWaterPumpCanteenApi({
    reusableCanteenOwned,
    reusableCanteenCharges,
    reusableCanteenCapacity,
    refillReusableCanteen,
    reusableCanteenStaminaCorePerDrink,
});
```

This avoids concurrent ownership of #88's implementation and lets either
module change its internals without coupling the other.

## Integration ownership

The integration agent must:

1. include `modules/water_pumps.cpp` after `modules/reusable_canteen.cpp`;
2. add/register the narrow #88 ownership accessor and callback table above;
3. call once per frame, before CoreClock reconciliation:

   ```cpp
   updateWaterPumps(player, ped, now, dead || locked, mission,
       &managedCore[1]);
   ```

4. run `python tools/reverse-engineering/verify_water_pumps_issue_89.py`;
5. perform the integration-owned build, install, hash verification, and GitHub
   state transition.

The interaction assets ship in the game. The requested map glyph adds an
issue-local `lex_blips` texture/linkage integration step described below. This
feature agent did not edit `script.cpp`, #88's module, shared build/install
files, `MyOverhaul/blipdata.ymt`, generated indexes, or GitHub state, and did
not compile/install.

## Water-pump map layer

The follow-up request was to create a custom icon and put all water pumps on
the map. Nearby `GET_CLOSEST_OBJECT_OF_TYPE` scanning cannot satisfy that: it
can see only streamed props. The map layer therefore uses the game's scenario
registry independently of the interaction scanner:

- a 20 by 20 overlapping grid covers world coordinates -8000 through +8000;
- each cell calls `GET_SCENARIO_POINTS_IN_AREA`
  (`0x345EC3B7EBDE1CB5`) with an 8192-entry `Any` buffer;
- each returned handle is filtered through `_GET_SCENARIO_POINT_TYPE`
  (`0xA92450B5AE687AAF`) for exactly `PROP_HUMAN_PUMP_WATER`;
- exact scenario coordinates are deduplicated and retained even if the point
  later unregisters; and
- every retained position receives a permanent coordinate blip named
  `Water Pump` using `LEX_BLIP_WATER_PUMP`.

The 400-cell sweep is spread across frames and repeats approximately every 20
seconds. Repetition is intentional: it accumulates chapter/interior points
that register later and, if this runtime exposes only streamed scenario
points, retains pumps as their areas stream. Saturated cells are logged rather
than silently presented as complete.

This is an exhaustive world-space query design, not an exhaustive coordinate
catalog. Static inspection cannot prove that Story Mode returns *unstreamed*
remote scenario points to this native. Therefore immediate all-pump coverage
remains a concrete runtime boundary: after the first sweep, the log and map
must confirm that remote towns receive markers without visiting them. If they
do not, authoritative `p_waterpump01x` placements must be extracted from the
level YMAPs after the currently running game releases its RPF file locks; a
streamed-neighborhood result must not be accepted as “all pumps.”

## Custom icon asset

`GameplayTweaks/icons/water-pump/` contains:

- a generated 32 by 32 RGBA pump silhouette with a fully transparent
  background and warm-white/black treatment matching the compact custom blips;
- its 32 by 32 DXT5 DDS;
- a deterministic Pillow source script;
- an issue-local build script that copies the existing nine DDS inputs, adds
  `lex_blip_water_pump`, and produces a ten-texture `lex_blips.ytd`; and
- a `LEX_BLIP_WATER_PUMP` blipdata fragment pointing at `lex_blips`.

Integration must merge the fragment into `MyOverhaul/blipdata.ymt` and place
the ten-texture issue-local YTD at `MyOverhaul/stream/lex_blips.ytd`. The module
requests `lex_blips` and logs both dictionary visibility and pre-request load
state once, avoiding the previously proven black-square failure mode.

## Runtime boundary / acceptance

Static evidence proves asset identity, scenario ownership, prop association,
alignment source, and reward-event names. It does not prove that an ASI-created
player-chore point will select each forced conditional variant or emit those
events in this Story Mode runtime. Testing must confirm:

1. both prompts appear only at unoccupied pumps and do not steal nearby prompts;
2. E aligns Arthur, moves the real handle, shows the authored drinking action,
   emits the drink event, restores the exact configured amount once, and exits;
3. R uses the authored bucket-fill presentation, emits a fill event, fills an
   owned partial canteen, and never changes Stamina Core;
4. no canteen/full canteen states are clear and cannot start R;
5. combat, ragdoll, mission transition, walking away during approach, and
   cancelling during the scenario exit cleanly; and
6. temporary points are removed and the pump remains usable afterward; and
7. after one complete grid sweep, known pumps in remote unvisited towns already
   have correctly rendered pump icons; otherwise runtime discovery is
   streaming-limited and the level-placement extraction fallback is required.

If the forced player variant or event does not fire, the log records entry and
timeout and the code deliberately grants nothing. That result calls for tracing
the authored camp point's prop/bucket setup, not replacing it with a guessed
animation or timer.

## Static validation

- `tools/reverse-engineering/verify_water_pumps_issue_89.py` checks that the
  module uses the exact authored scenario/variants/prop/events, that source data
  contains them, that reward calls are downstream of event gating, and that no
  loose animation/scenario-position fallback was added. It also checks the
  world-grid scenario query, exact type filter, marker linkage/name, texture
  request, RGBA transparency, DXT5 payload, and issue-local build inputs.
- Feature-file `git diff --check` passed.
