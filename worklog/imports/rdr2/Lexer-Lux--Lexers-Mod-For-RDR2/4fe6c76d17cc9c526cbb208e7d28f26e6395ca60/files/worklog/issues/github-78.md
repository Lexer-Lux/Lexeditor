# Worklog: Github 78

## GitHub #78 zero-bar Dead Eye reactivation — 2026-08-05

The previous no-reserve implementation used `_GET_PLAYER_DEAD_EYE`, an absolute
point amount, inferred its maximum from the session, and made a stateless cutoff
decision every frame. Disabling Dead Eye could make that reading bounce above
the inferred cutoff, so GameplayTweaks re-enabled the ability. That allowed a
new activation with a visibly empty bar and could leave it active indefinitely.

Rockstar's Story scripts use `_GET_PLAYER_DEAD_EYE_METER_LEVEL(player, true)`
for exact zero/nonzero Dead Eye checks. GameplayTweaks now uses that normalized
0..1 meter for the configured cutoff and latches exhaustion. While latched it
ends the ability and blocks all four special-ability controls every frame. The
latch can clear only while Dead Eye is inactive and the meter has genuinely
refilled two percentage points above the cutoff; an attempted empty-bar
activation therefore cannot unlock itself. A falling Dead Eye core while active
also raises the same latch after restoring the slipped reserve tick.

GameplayTweaks built successfully with the two pre-existing C4838 warnings. The
748032-byte ASI hashes
`8A60243F67D6790CDBAFECE4BC12345F5771D2E5F412E196D4FC3D2A8785B727`.
RDR2 was running; corrected watcher PID 406808 will install and hash-verify this
build after exit. Runtime acceptance requires exhausting Dead Eye, rejecting a
second zero-bar activation, then refilling it and confirming activation returns.

## Active-ability correction

The latch disabled future activation but did not reliably terminate Dead Eye
already in progress. Exhaustion now uses either the rendered outer-bar floor or
normalized threshold and explicitly deactivates an active special ability every
latched frame before blocking activation controls.

## Live zero-bar correction

The next failure trace showed `_GET_PLAYER_DEAD_EYE` repeatedly bottoming at
roughly 25-28 points while the user-visible outer ring was already zero, and the
installed TRUE-form meter latch never fired. The implementation had incorrectly
described `_GET_PLAYER_DEAD_EYE_METER_LEVEL(player, TRUE)` as the proven
normalized form; in practice it never crossed the 0.15 latch, so neither
deactivation nor control blocking ran.

Story Mode's `shop_doctor.c` uses the FALSE form and compares it directly to
`0.5`, proving that form is the normalized 0..1 meter. The controller now uses
FALSE and a one-percent empty tolerance. Once that visible meter crosses the
floor it latches, calls `DEACTIVATE_SPECIAL_ABILITY` while active, disables the
ability, and releases only after an inactive genuine refill above hysteresis.

## 2026-08-07 — why every one of the above still failed

Lexer, 2026-08-06T11:26Z: "now i can just use deadeye forever. my bar drains,
hits 0, and i'm still in deadeye." Then 12:58Z: "nothing has been changed."
Both reports are correct, and the reason is that **the exhaustion latch had no
reachable trigger.** Three independent defects, each verified against a primary
source rather than inferred.

### 1. `GET_DEADEYE_BAR` is not a bar and not a percentage

`0xA81D24AE0AF99A5E` is `_GET_PLAYER_DEAD_EYE`
(`_downloads/NativeMenuBase/RDR2-Native-Menu-Base-master/inc/natives.h:7897`) —
the raw absolute Dead Eye amount, i.e. outer ring *plus* the core reserve this
item exists to fence off. It is the same native the top of this file already
records as unusable for exactly this purpose, re-adopted under a name that says
"bar".

Runtime proof, `GameplayTweaks.reserve.log` from the installed build:

    stamina=28.3348 core=16 ... deadeye=133.56 core=77 active=0 disabled=0 locked=1

`133.56` on a value the code compared against `10.0` as a percent and against
`0.01` as "empty". Two decisive comparisons, both unreachable:

- CoreClock loop: `deadeyeBarFloor = GET_DEADEYE_BAR(player) <=
  g_reserveBarFloor` (10.0, `BarFloorPercent`). Never true, so **the Dead Eye
  core had no reserve protection in the CoreClock pin at all**.
- Latch: `deadeyeBar <= 0.01f`. Never true; this file already records the value
  bottoming at ~25-28 with the ring rendered empty.

### 2. CoreClock erased the reserve tick before the detector could read it

The one scale-free detector already present — "a falling Dead Eye core while
Dead Eye is active is a reserve spend" — read the core with `GET_CORE(ped, 2)`
*after* the CoreClock block had already run in the same frame. CoreClock's
symmetric one-point hold

    else if (live != managedCore[core]) SET_CORE(ped, core, managedCore[core]);

restores a single-point drop immediately. A reserve tick is a single point. So
`liveDeadeyeCore < previousDeadeyeCore` could never once be true. The hold was
added for a real reason (the flashing core-state haze) and is not at fault; the
*ordering* was. This is why "nothing has been changed" was an accurate report of
a build that did contain changes.

### 3. `DEACTIVATE_SPECIAL_ABILITY` was a fabricated name on a wrong-arity call

    static void DEACTIVATE_SPECIAL_ABILITY(Player p) { invoke<Void>(0x1D77B47AFA584E90, p); }

`0x1D77B47AFA584E90` is `_SPECIAL_ABILITY_START_RESTORE(Player player, int p1,
BOOL p2)` (`natives.h:7882`) — three arguments, and a *restore*, not a
deactivate. All 20 Story Mode call sites pass three, e.g. `gang1.c:25440`:

    PLAYER::_0x1D77B47AFA584E90(PLAYER::PLAYER_ID(), -1, true);

The wrapper passed one, so p1/p2 were read from unset argument slots — every
frame the latch held, with the ability active. Rockstar's own end-Dead-Eye idiom
needs this native not at all; where they want an active ability stopped they
test `0xB16223CB7DA965F0` and call `0xAE637BB8EF017875(player, 1)`
(`SET_DEADEYE_DISABLED`), verified at `abigail2_1.c:75189-75191` and again
unconditionally at `abigail2_1.c:83858-83860`. The latch already did that.

### What changed

- The exhaustion trigger is now **only** the refused reserve tick
  (`deadeyeReserveTick`), which needs no scale and no threshold.
- Dead Eye's live core and active flag are sampled **before** the CoreClock
  block, the only point in the frame where the tick is still visible.
- The CoreClock pin for core 2 is gated on "Dead Eye is active" instead of the
  impossible percent comparison. Correct in both configurations: with CoreClock
  disabled the pin does not run, and the standalone detector — which keeps its
  own `previousDeadeyeCore` baseline — is then unobstructed.
- `0x1D77B47AFA584E90` is gone. `SET_DEADEYE_DISABLED(true)` is issued on the
  latch edge only; `DISABLE_CONTROL` stays per-frame because it expires per
  frame by design.
- `GET_DEADEYE_BAR` renamed `GET_DEADEYE_RAW` with the scale documented. An
  alias keeps #125's `updateDeadeyeConsumption` and
  `modules/combat_inventory.cpp:744` compiling untouched — those use it as a
  closed-loop *rate* measurement, where the absolute scale cancels and the value
  is sound.
- The `_GET_PLAYER_DEAD_EYE_METER_LEVEL` comment claiming FALSE is "the
  normalized visible meter" is corrected. The `shop_doctor.c:11014` / `:11049`
  `< 0.5f` citation is real, but it establishes only that the form is
  normalized — **not** that it tracks the outer ring rather than the core.
  `rcm_bh_skinner_search.c:19848/:19853` tests the TRUE form for exactly `0f`
  during play. Neither form is proven; both are now logged side by side
  (`meterF` / `meterT`) so one session settles it, and neither gates behaviour.
- `deadeyeOuterEmpty()` survives: an edit in this pass deleted it as "never
  called" after grepping only `script.cpp`. `modules/combat_inventory.cpp:613`
  calls it. Restored unchanged; recorded because it is the same one-file-grep
  error as fuckups.txt entry 17.

### Diagnostics

`GameplayTweaks.reserve.log` gains `deadeyeRaw`, `meterF`, `meterT`, `dexh`
(latch) and `dtick` (trigger), plus `noReserve`. A line reading
`active=1 dexh=0 dtick=0` with the ring empty now *proves* the trigger did not
fire rather than leaving a silent log. An idle heartbeat covers the no-ped case:
the entire controller lives inside `if (ped)`, and the shipped log was two lines
— both `locked=1`, so the feature block never executed once — which was
indistinguishable from "ran and saw nothing". Both writers share one truncation
flag so neither wipes the other.

### Not fixed: the horse-gait report (2026-08-06T18:54Z)

> "if i run out of horse stamina, it won't run into its core. good. but, it
> never starts regenerating again unless i intentionally slow it with ctrl."

Diagnosed, not changed. `horseMovementStaminaRate()`
(`modules/movement.cpp:113-128`) is banded on **ground speed**, and the only
positive bands are below 5.0 m/s (standing +16, walking +8, trotting +2);
cantering is -6 and galloping -14 (`GameplayTweaks.ini [HorseStamina]`, lines
57-64). On exhaustion the controller sets `SET_PED_STAMINA_DEPLETION(mount, 0)`,
clamps a negative rate to `0.0f`, and calls
`DISABLE_CONTROL(INPUT_HORSE_SPRINT)`. Disabling that input does **not** lower a
horse's gait the way disabling `INPUT_SPRINT` drops the player out of a sprint —
the player's sprint is a held input, the horse's gait is retained state. So the
horse coasts on above 5.0 m/s, the rate stays negative, the exhausted clamp
turns it into exactly zero, and the bar neither drains nor recovers until the
rider presses slow-down. That is precisely the reported symptom, including why
Ctrl fixes it.

The sanctioned engine path is almost certainly `SIMULATE_PLAYER_INPUT_GAIT` /
`RESET_PLAYER_INPUT_GAIT` (`0xFA0C063C422C4355` / `0x61A2EECAB274829B`,
`natives.h:7980-7981`), used ~830 times across `script_rel`. **Its parameters
are not what natives.h names them** — the corpus shows
`(PLAYER_ID(), amount, durationMs, heading, bool, bool)`, e.g.
`(PLAYER_ID(), 1f, 2000, 0f, true, false)` ×32 and
`(PLAYER_ID(), 2.5f, 4000, func_1516(0, 12), false, false)`. The third argument
is a duration in milliseconds, not a "gaitType". Shipping a per-frame input
simulation on a player-controlled mount with inferred argument semantics is the
fuckups.txt entry 6 pattern (per-frame war with the engine) layered on the entry
1 pattern (unresolved constants), so it is deliberately **not** in this change.
`horseSpeed`, `horseMode`, `horseRawRate` and `horseExh` were added to the trace
so the next pass acts on measurement.

### Safety

No `SET_ATTRIBUTE_POINTS` and no `SET_ATTRIBUTE_BASE_RANK` anywhere in this
change (fuckups.txt entry 8). Core writes remain `SET_CORE` / `SET_HORSE_CORE`,
both hardcoded to `0xC6258F41D86676E0` (`_SET_ATTRIBUTE_CORE_VALUE`).
Separately worth knowing: `[CoreClock] WriteMode=0` is **not a guard** — grep
finds the key only in `GameplayTweaks.ini:155`; no code reads it. The real
protection is the hardcoded native in `SET_CORE`. Nothing here defeats either.

## 2026-08-09 Eagle Eye input regression

Lexer reported that MMB no longer activated Eagle Eye. The exhaustion latch was
disabling `INPUT_SPECIAL_ABILITY` and all three related actions every frame.
RDR2 contextually uses that shared MMB action for Eagle Eye while the player is
not aiming, so the Dead Eye block had globally removed an unrelated vanilla
ability for as long as the latch remained set.

The four shared-control suppressions were removed. The existing
`SET_DEADEYE_DISABLED` edge remains the sole Dead Eye activation block; it does
not consume the common MMB action. The static verifier now rejects any return of
shared special-ability control suppression inside the exhaustion block.

Development ASI
`F1852A53EA48C933C9E12420E3CC8589C34E3D8FA4FCA0D31EE63B28DC89BF28`
was built and installed while RDR2 was closed. Source, game-root ASI and release
manifest hashes matched. Runtime acceptance requires ordinary MMB Eagle Eye,
then empty-ring Dead Eye rejection, then MMB Eagle Eye again while that Dead Eye
latch remains active.

