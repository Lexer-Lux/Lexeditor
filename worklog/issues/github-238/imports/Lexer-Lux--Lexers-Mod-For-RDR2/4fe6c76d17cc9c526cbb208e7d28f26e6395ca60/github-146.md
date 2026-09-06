# GitHub #146 - Block Items That Would Reduce a Core Below Zero

## Live player-facing contract

An item with one or more negative player-core effects is greyed and cannot be
activated whenever its full configured negative cost would take Health,
Stamina, or Dead Eye below zero. An exact-zero result remains usable. Positive
and zero effects are ignored; one insufficient core blocks a multi-core item as
one transaction. Radial, satchel, quick-use, and contextual paths must agree,
and a rejected attempt must not consume, animate, or partially apply the item.

## Authoritative effect audit

`MyOverhaul/catalog_sp.ymt` is the installed overhaul's source of item effect
references and effect values. Walking every catalog item, resolving its
`effectids` entry, and retaining only negative `EFFECT_HEALTH_CORE`,
`EFFECT_STAMINA_CORE`, and `EFFECT_DEADEYE_CORE` entries produced 15 items:

- `CONSUMABLE_JERKY`: Stamina 6.25;
- `CONSUMABLE_MOONSHINE`: Stamina 50 and Dead Eye 50;
- `CONSUMABLE_WHISKEY`, `CONSUMABLE_BRANDY`, `CONSUMABLE_RUM`,
  `CONSUMABLE_GIN`, `CONSUMABLE_SALOON_BEER`: Dead Eye 12.5;
- `CONSUMABLE_CIGARETTE_BOX_CHEAP`, `CONSUMABLE_OFFAL`,
  `CONSUMABLE_CRACKERS`, `CONSUMABLE_JERKY_VENISON`,
  `CONSUMABLE_BISCUIT_BOX`, `CONSUMABLE_CIGARETTE_BOX`, and
  `CONSUMABLE_MEAL_CHILLI`: Stamina 12.5;
- `CONSUMABLE_SALOON_WHISKEY`: Stamina 12.5 and Dead Eye 12.5.

No current overhaul item references a negative Health-core effect, but the
implementation resolves and evaluates Health identically so a later configured
Health cost is supported once its item enters the verifier-generated candidate
set.

The amounts above are percentages on the displayed 0..100 core scale, not the
catalog's small integer `value` field. `generic_single_use_item.c` fills live
effect IDs with `_ITEM_DATABASE_FILLOUT_ITEM_EFFECTS_IDS`, fills each seven-slot
record with `_ITEM_DATABASE_FILLOUT_ITEM_EFFECTS_ID_INFO`, and its `func_23`
uses `percent / 100 * 200` when percent is nonzero. It uses `value / 8 * 200`
only when percent is zero. The item script's internal core store is -100..100,
then converted to the HUD/native 0..100 core value; therefore the effective
displayed cost is exactly negative percent, or negative `value / 8 * 100` for
the fallback.

## Relevant use paths

`short_update.c::func_2135` is Rockstar's shared inventory-availability path.
It calls `_INVENTORY_DISABLE_ITEM(inventoryId, item, 0)` for unavailable items
and `_INVENTORY_ENABLE_ITEM` for available items while building the live player
inventory. This is the authoritative cross-surface mechanism: disabled items
remain present but grey/unavailable to the radial and satchel, and normal
inventory-backed activation cannot begin.

The same script chooses the quick-use item into
`Global_1935496.f_67.f_2` and exposes `INPUT_QUICK_USE_ITEM`. Because that choice
can be cached before a core changes, the module additionally suppresses the
quick-use action whenever the cached item is currently blocked.

Direct/contextual scripts can call `TASK_ITEM_INTERACTION` without opening an
inventory surface. The normal paths cannot reach that point for a disabled
item. As a last race shield, the module watches the authoritative current item
interaction and immediately clears a blocked interaction before the generic
item script's authored effect/consume animation event. It does not compensate
with an inventory add, core write, or partial-effect rewrite.

## Issue-local implementation

`GameplayTweaks/modules/core_cost_guard.cpp` contains only the 15 candidate
names discovered from the current catalog; their values are not hardcoded. At
runtime it resolves the loaded ITEM_DATABASE effects and sums only negative
entries per core. The verifier reparses the overhaul catalog and fails if the
candidate set or key multi-core costs drift.

The current core read comes from `Global_40.f_11095[0..2]`, the exact float
source the generic item scripts mutate, converted from -100..100 to 0..100.
This preserves fractional 6.25/12.5 thresholds; `_GET_ATTRIBUTE_CORE_VALUE` is
the bounded fallback if the live global is outside its authoritative range.
The comparison is strictly `current < cost`, so equality is allowed.

Blocked items are re-disabled every update because Rockstar `short_update`
refreshes item availability in rolling batches. This per-frame ownership is
limited to currently blocked items and is necessary to prevent a one-frame
activation reopening. Unblocked items receive a single enable transition;
items that this feature does not own are never enabled. Hot-disabling the
feature restores only items it had blocked. Transition and five-second
heartbeat logs record resolved count, blocked count, all three cores, selected
quick-use item, costs, and inventory counts.

## Integration handoff

The integration owner must:

1. include `modules/core_cost_guard.cpp` after the common native/global helpers;
2. call `updateCoreCostGuard(ped, now, dead || SCREEN_FADED_OUT())` once per
   update, after UI/item systems so its availability decision is final for the
   frame;
3. add `[CoreCostGuard]` with `Enabled=1` to the integration-owned INI.

No shared dispatcher, INI, manifest, build, install, or GitHub label was changed
in this issue-local handoff.

## Static result and runtime boundary

`python tools/reverse-engineering/verify_core_cost_guard_issue_146.py` verifies
the catalog-derived 15-item set and exact costs, the five native hashes,
Rockstar's effect conversion and inventory enable/disable paths, strict
less-than comparison, per-core multi-effect accumulation, quick-use cache
suppression, contextual interaction rejection, and the absence of consume,
inventory compensation, core mutation, or replacement-animation code.

Runtime acceptance is still required. The native inventory disable path is the
authoritative greying mechanism, but only the rendered radial/satchel can prove
the grey presentation and only in-game counts/animations can prove no
activation escaped. A direct third-party `START_ITEM_INTERACTION` bypass is
observable only on its first running frame; the module clears it there, but a
foreign script that applies effects before exposing the interaction would need
coordination in that script and cannot be proven safe statically.
## 2026-08-10 combined release

- Release ASI built successfully: `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`.
- RDR2 was running, so one hidden payload-only installer was queued. The issue remained actionable pending game-root hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
## fuckups.txt recurrence audit

- Catalog parsing and a disabled-item setter are not sufficient if Rockstar re-enables the item later in the same update or quick-use bypasses the inventory surface.
- The guard resolves the loaded negative effects, compares the live core store, reasserts canonical availability after other item updates, blocks cached quick-use, and logs bypass cancellation. Zero-core cigarettes and multi-core items remain runtime acceptance cases.

## 2026-08-10 runtime-returned effect-buffer repair

Lexer reported that cigarettes remained usable at zero Stamina. The unified
log proved this was not a late enable race: every heartbeat said
`resolved=0/15`, and every candidate repeatedly logged `effect lookup not
ready`. The guard therefore never reached its availability decision at all.

The C++ representation of Rockstar's script fixed array was one slot short.
`short_update.c` sets `Var0.f_1 = 20`, passes `&Var0`, reads the count from
`Var0`, and indexes IDs through `Var0.f_1[i]`. Slot `f_1` is the fixed-array
capacity header; element zero begins after it. The old struct stored the
capacity in `ids[0]`, then passed that literal `20` to the effect-info native as
the first effect ID. That lookup failed, so all 15 items remained unresolved.

`CoreCostEffectIds` now has explicit `count`, `capacity`, and `ids[20]` fields.
The loader writes `capacity=20` and indexes only the values after that header.
The verifier pins the exact two authoritative `short_update.c` layouts and
rejects the old `ids.ids[0] = 20` form.

After the next integrated install, acceptance begins with the diagnostic
postcondition `resolved=15/15`; any lower value is an immediate failure and is
not a reason to ask Lexer to test UI behavior. Only then are the original
zero-core cigarette, equality, multi-core, radial, satchel, quick-use, and
contextual tests meaningful.

## 2026-08-10 actionable recurrence audit: per-frame availability writes

- **Primary evidence:** the installed unified log reported
  `resolved=15/15 blocked=15` during the failed shop interaction.  Direct
  source inspection showed that the blocked branch called
  `_INVENTORY_DISABLE_ITEM` for every blocked item on every update.  The #114
  shop trace ran earlier in the dispatcher, so its `inventoryBusy=0` sample did
  not cover these later calls.
- **Reference path:** `short_update.c::func_845` processes inventory
  availability in bounded 150-item batches when its inventory revision is
  unsettled, and `func_2135` uses the same enable/disable natives.  Story
  satchel code reads `_0x3D10D7179D7034AF` as the disabled-item predicate
  (`satchel_ui_event_handler.c::func_110` returns early when it is true).
  These sources support transition ownership and readback; they do not
  support a permanent 15-writes-per-frame fight.
- **Sanctioned repair:** write on a real blocked/restored edge.  If Rockstar
  completes a later inventory revision, perform one bounded reconciliation
  after that revision settles, subject to a cooldown, and only write when the
  Story availability readback disagrees.  Record attempts, successful
  readbacks, and failures.  Keep quick-use and direct-interaction rejection,
  because those are event/gate paths rather than inventory mutation loops.
- **Acceptance boundary:** `resolved=15/15`, transition/readback logs, and a
  bounded idle write count are implementation postconditions.  Only rendered
  radial/satchel state can prove greying, and only player tests can prove exact
  zero is allowed, below-zero is rejected, no item is consumed, and shop
  ownership remains stable.

### Coupled implementation result

The steady blocked branch no longer calls `_INVENTORY_DISABLE_ITEM`.  A block
or restore is now an owned transition.  After `short_update` advances
`Global_1935496.f_28` to the requested revision in `.f_27`, one bounded
reconciliation can correct a later Rockstar availability refresh.  The same
item has a five-second minimum between writes.  A failed setter readback can be
retried at that cadence, but a confirmed steady state performs no write.

The readback is native `0x3D10D7179D7034AF`.  This is not an invented name:
`satchel_ui_event_handler.c::func_110` uses a true result to reject ordinary
item use.  The module therefore records `beforeDisabled`, `afterDisabled`, and
`confirmed` around the matching enable/disable native.  It does not claim
success from the void setter call.  If another Story rule had already disabled
the item, the module does not claim ownership and does not later enable it.

The direct/contextual bypass also changed from one disable/clear pair per frame
to one pair on the newly observed interaction edge.  Quick-use control
suppression remains frame-scoped because control disabling is itself a
frame-scoped input contract and performs no inventory mutation.

Static checks passed for #146, #114, carried-mask #77, camp policy #1, and
dual-wield #151.  RDR2 was not running, so runtime write counts and rendered
greying are untested.  The issue remains actionable until integration builds
and installs it; after that, acceptance still requires both the original item
tests and stable shop ownership.

## 2026-08-11 startup and active-transaction correction

The edge/revision repair still had two unsafe mutation windows. A low-core save
could issue up to 15 availability writes as soon as the player existed, while
Rockstar was still starting shop and inventory owners. The direct-interaction
fallback also called `_INVENTORY_DISABLE_ITEM` after an item interaction had
already acquired the ped, opening another inventory mutation inside the exact
transaction it was trying to reject.

Before this change, `fuckups.txt` was read again. The relevant recurrence
classes were the prior per-frame engine fight, intent-only setter success, and
shop damage from unrelated background inventory work. The same primary sources
remain authoritative: `short_update.c::func_845/func_2135` owns availability
refreshes, and `satchel_ui_event_handler.c::func_110` reads native
`0x3D10D7179D7034AF` as the disabled-item predicate.

Availability writes and feature-disable restoration now require 15 seconds of
settled player state and yield while the radial, backup inventory, or an item
interaction is active. The direct-interaction path clears the blocked action
once but no longer writes inventory state inside that action. Quick-use control
suppression remains frame-scoped because it is an input gate, not an inventory
mutation. Heartbeats now expose `mutationSafe`, wheel, backup-inventory, and
interaction state so a deferred write is distinct from a failed write.

Static checks passed:

```
python tools/reverse-engineering/verify_core_cost_guard_issue_146.py
PASS: #146 exactly covers all 15 configured negative-core items, uses runtime item effects, allows equality, uses edge/revision availability writes with Story readback outside startup/UI transactions, and guards inventory/quick/context paths

python -m py_compile tools/reverse-engineering/verify_core_cost_guard_issue_146.py
PASS

git diff --check -- GameplayTweaks/modules/core_cost_guard.cpp tools/reverse-engineering/verify_core_cost_guard_issue_146.py worklog/issues/github-146.md
PASS
```

Integration must restore the existing module call only after shop-startup
protection. Runtime acceptance still starts with `resolved=15/15`, followed by
grey/unusable tests below cost, usable-at-equality, one insufficient core in a
multi-core item, no consumption/animation on rejection, immediate restoration,
and unchanged shop/minimap interaction.
