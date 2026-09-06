# GitHub #151 - second handgun slot disappeared

## Live report and installed evidence

The full live issue had no comments. Lexer reported that while testing the
mouse-wheel ammunition changer, his second holster disappeared and the weapon
wheel returned to one handgun slot. The attached 2560x1440 screenshot was
downloaded and inspected before implementation. It shows the weapon wheel in
the single-wield layout with one top `SIDEARMS` segment. It does **not** show
Arthur's waist clearly enough to prove that an off-hand clothing inventory item
was deleted.

The installed ASI at investigation time was SHA-256
`CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
The installed unified log captured the returned sequence:

```
[radial-ammo] ammo-cycle requested direction=forward weapon=0x1765a8f8 before=0x90083d3b action=0xf1421cf5
[radial-ammo] ammo-cycle requested direction=forward weapon=0x1765a8f8 before=0x90083d3b action=0xf1421cf5
[radial-ammo] ammo-cycle requested direction=backward weapon=0x1765a8f8 before=0x90083d3b action=0xd9f9f017
[radial-ammo] ammo-cycle requested direction=forward weapon=0x1765a8f8 before=0x90083d3b action=0xf1421cf5
[radial-ammo] ammo-cycle requested direction=forward weapon=0x1765a8f8 before=0x90083d3b action=0xf1421cf5
[radial-ammo] ammo-cycle ignored weapon=0x1765a8f8 unchanged=0x90083d3b
```

The weapon hash resolves from `MyOverhaul/weapons.ymt`, `catalog_sp.ymt` and
`quickselectitems.ymt` to `WEAPON_SHOTGUN_SAWEDOFF`. The two action hashes
resolve in `_downloads/rdr3_discoveries/Controls/README.md:600,604` to
`INPUT_QUICK_SELECT_SECONDARY_NAV_NEXT/PREV`. The extracted
`sub_slot_list.ymt.rbf.xml:114,177` binds those actions to the ammo option
stepper. Nevertheless the required ammo-type readback never changed. That
proves the synthetic translation failed its own postcondition; temporal
adjacency alone does not prove which engine state removed the dual-wield layout.

RDR2 had exited by the time the repair source was prepared, so live ped state
could not be queried from the ended process. No claim about the current save's
clothing record or unlock state is made from the screenshot.

## `fuckups.txt` recurrence audit before code

### Primary evidence/reference

- `_downloads/natives.json:122525-122559` resolves `0x918990BD9CE08582` as
  `GET_ALLOW_DUAL_WIELD(Ped)` and `0x83B8D50EB9446BBA` as
  `_SET_ALLOW_DUAL_WIELD(Ped, BOOL)`. These are a matched readback/setter pair;
  neither name nor signature is inferred.
- `short_update.c:86012-86017` is Rockstar's enable path for progression case
  24: set `SP_WEAPON_DUALWIELD` unlocked and visible, then call
  `_SET_ALLOW_DUAL_WIELD(playerPed, 1)`. Its disable path at :86268-86272 uses
  the same three operations with unlocked=false and allow=0.
- `act_hunting_2.c:26321-26338` repeats the same enable sequence and then checks
  the equipped `MP_COMPONENT_TYPE_LOADOUT_3` record. Its component-index map at
  `func_444` (`:17815-17820`) resolves LOADOUT_3 to index 27. `func_799`
  (`:30179-30186`) defines "equipped" as
  `Global_1946804.f_1497.f_1[27] != Global_1946804.f_57[27]`.
- Extracted `quickselectmenus_ymt.xml:5-25,119-151` independently proves the
  screenshot's layout transition. The single-wield provider is active when
  `CAIConditionIsDualWieldAvailable`/`CAIConditionIsDualWieldUnlocked` are
  absent; the dual-wield provider requires either availability or the unlocked
  state while horse inventory is reachable. This is why the matched allow and
  unlock readbacks are the correct engine state to observe rather than an
  invented "second holster present" global.
- The recurrence audit does not treat an unlock setter call as success.
  `GET_ALLOW_DUAL_WIELD` must positively read true afterward.

### Sanctioned path

Repair only the runtime allow flag through Rockstar's exact progression path,
and only when existing state proves the player is entitled to it: either the
`SP_WEAPON_DUALWIELD` unlock is already true or the resolved LOADOUT_3 component
is non-default. Do not invent an inventory GUID, grant an off-hand item, or
write either clothing global. When the component proves entitlement but the
unlock is false, restore the same named unlock+visibility state Rockstar does,
then call the allow setter once. A mission gate yields to Story transitions.

### Execution proof and diagnostics

At bounded cadence, log the matched native readback, named unlock readback,
resolved current/default LOADOUT_3 hashes, wheel-open state and highlighted
weapon. On a false allow state with entitlement, log the complete before state,
issue Rockstar's transition once, then log the immediate and next-poll
`GET_ALLOW_DUAL_WIELD` postcondition. A three-second idle heartbeat distinguishes
"module not running" from "dual wield stayed healthy". Never truncate the
unified log locally.

### Player-visible acceptance

The weapon wheel must retain two sidearm/dual-wield capacity after repeated
mouse-wheel tests over the centre and weapon segments, after closing/reopening
the wheel, and after a save/reload. Both equipped sidearms must still draw and
fire together. Arthur/John's actual off-hand holster clothing must remain
visible. The diagnostic readback establishes only engine permission; the wheel,
weapons and clothing are separate visible acceptance checks.

### Every issue-owned per-frame native

The repair must add **no per-frame native**. Permission, unlock, component and
wheel correlation checks are bounded. The existing #130 path is called every
frame but only reads wheel state while open; its only mutation is a debounced
`SET_CONTROL_VALUE_NEXT_FRAME`. The installed unchanged ammo readback means that
mutation is not accepted as working and must not be used as proof of this
repair's success.

## Issue-local repair prepared

`GameplayTweaks/modules/dual_wield_guard.cpp` now samples at 4 Hz and uses the
matched `GET_ALLOW_DUAL_WIELD` readback. It performs one repair attempt per
observed allowed-to-blocked transition, only when the named unlock or resolved
non-default LOADOUT_3 proves entitlement. A failed setter is latched instead of
being repeated every poll; only a later true readback can re-arm the guard. The
module also emits three-second active, mission-gated and no-ped heartbeats.

The exact broken postcondition visible in the report is loss of the engine's
dual-wield availability state: the wheel chose its single-wield provider. The
historical log proves the adjacent synthetic ammo requests failed, but it did
not record `GET_ALLOW_DUAL_WIELD` at the instant of loss, so the precise engine
writer that cleared permission remains unknown. The repair therefore observes
and restores the sanctioned state without claiming that scroll input was the
causal writer.

`tools/reverse-engineering/verify_dual_wield_guard_issue_151.py` resolves both
native hashes from `natives.json`, checks Rockstar's progression ordering and
LOADOUT_3 algebra, requires bounded cadence/heartbeats and both readbacks, and
rejects input synthesis, weapon grants, inventory additions and clothing-global
writes.

Static checks passed:

```
python tools/reverse-engineering/verify_dual_wield_guard_issue_151.py
PASS #151: bounded Story dual-wield transition uses matched readback/setter, requires earned entitlement, and never writes inventory or clothing globals

python -m py_compile tools/reverse-engineering/verify_dual_wield_guard_issue_151.py
PASS
```

Integration must include the new module and call
`updateDualWieldGuard(ped, now, mission)` after the radial-ammo update. The call
may occur from the shared frame dispatcher because the module enforces its own
250 ms cadence. Integration alone is not runtime acceptance; the player-visible
checks above and the log's immediate plus next-poll allow readbacks are still
required in game.

## 2026-08-10 returned failure recurrence audit before further code

### Primary evidence/reference

- The live issue body says the second holster disappeared while testing the
  mouse-wheel ammo path; the latest comment says the player still has only one
  handgun holster. Neither statement by itself identifies which of four
  separate states failed: wheel provider/layout, the physical off-hand holster
  clothing component, earned dual-wield progression, or the ped's current
  `GET_ALLOW_DUAL_WIELD` permission.
- The prior installed radial-ammo trace proves only that synthetic secondary-nav
  actions were attempted and the ammo hash did not change. Temporal adjacency
  is not proof that #130 cleared dual wield.
- The matched permission getter/setter and Rockstar progression/component
  references recorded above remain the only sanctioned dual-wield evidence.
  The next audit must read current installed execution/postconditions rather
  than treating the existing verifier or setter call as runtime success.
- The #114 carried-mask inventory-write repair is a separate background writer
  concern. It must be inspected for inventory/loadout writes, but it is not a
  cause unless an actual overlapping write or runtime transition is found.

### Sanctioned path

- Observe the named unlock, LOADOUT_3 current/default component, matched ped
  allow readback, wheel state, and equipped sidearms independently at bounded
  cadence. Repair only a false allow state when earned entitlement is proven.
- Do not grant a holster, invent an inventory GUID, rewrite clothing globals,
  manufacture progression, or force a dual-wield wheel provider. If permission
  is already true while the physical holster or wheel remains absent, stop and
  report that distinct failed layer instead of repeatedly calling the setter.

### Actual execution/postcondition requirement

- Confirm the new module is registered in the installed artifact and look for
  its idle heartbeat. Absence of `[dual-wield]` is `not executed` until proven
  otherwise, never evidence that state remained healthy.
- A repair attempt counts only when the log contains the before readbacks, the
  matched setter call, an immediate getter readback, and a later poll that still
  reads allowed. Setter intent alone is not success.

### Player-visible acceptance

- Weapon wheel: two sidearm slots/providers remain available after repeated
  centre/weapon-segment scroll tests and wheel reopen.
- Physical equipment: Arthur/John visibly retains the off-hand holster model.
- Progression/inventory: earned dual-wield unlock and LOADOUT_3 entitlement
  remain present without granting or replacing an item.
- Runtime capability: two equipped handguns draw and fire together after a
  save/reload. A true native allow readback does not substitute for any of these
  visible checks.

### Every issue-owned per-frame native

- No new per-frame native is permitted. The issue-owned guard may be called by
  the shared dispatcher, but all getter/component/wheel polls remain behind its
  250 ms gate and heartbeats remain at three seconds. Mutations may occur once
  per proven true-to-false permission transition only, with a failed attempt
  latched rather than retried every poll.

## 2026-08-10 returned failure: permission hypothesis disproved

The installed unified log proved that the first guard executed continuously,
but also disproved its proposed repair target:

```
[dual-wield] state allow=1 unlock=1 loadout3=0x0 default=0x3f800000 ...
[dual-wield] heartbeat gate=active allow=1 unlock=1 equippedLoadout3=0 ... repairs=0
```

`GET_ALLOW_DUAL_WIELD` was already true and `SP_WEAPON_DUALWIELD` was already
unlocked while Lexer still had one visible holster and one handgun slot. The
permission setter therefore cannot repair this returned failure. The module's
reported default `0x3f800000` exposed a second defect: it read
`Global_1946804.f_57[27 /*11*/]` without skipping that fixed array's length
header. The correct flattened addresses are:

- current `Global_1946804.f_1497.f_1[27 /*3*/]`:
  `1946804 + 1497 + 1 + 27 * 3`;
- default `Global_1946804.f_57[27 /*11*/]`:
  `1946804 + 57 + 1 + 27 * 11`.

With that correction, the installed `loadout3=0x0` is the concrete missing
layer: the current off-hand holster component is empty. This is distinct from
permission, progression and the wheel's presentation.

### Reconciliation with #130 and #114

`updateRadialAmmoScroll` was re-read in `modules/recon.cpp`. Its only mutation
is one debounced `SET_CONTROL_NEXT_FRAME` for Rockstar's secondary-nav action;
it contains no inventory add/remove, weapon grant, current-weapon setter or
clothing write. Its installed ammo readback stayed unchanged, so #130 did not
prove either success or causation of the missing holster.

The current #114 carried-mask repair was also re-read. All inventory/clothing
mutation is below `weaponWheelTransactionBusy(now)`, availability writes occur
only on a changed availability edge, hidden state only after a proxy change or
inventory creation, and clothing-active/cache refresh only on a real worn-state
edge. It shares the inventory layer and therefore remains relevant to runtime
acceptance, but no direct LOADOUT_3 write or installed transition tied it to
this missing component. No #114-owned file was changed for #151.

### Evidence-backed recovery

Rockstar's `act_hunting_2.c` progression case 24 supplies the exact recovery
contract for an earned but missing LOADOUT_3 component:

1. require the named `SP_WEAPON_DUALWIELD` entitlement;
2. select `CLOTHING_SP_OFFHAND_000` for Arthur or item `-1515874150` for John;
3. add that clothing item only if it is absent;
4. equip it as `MP_COMPONENT_TYPE_LOADOUT_3` and enable dual wield.

`dual_wield_guard.cpp` now follows that contract once per observed missing
component episode. It yields during missions, while the weapon wheel is open,
while an item interaction owns the ped, while player control is unavailable,
and while `_INVENTORY_IS_USING_BACKUP_INVENTORY` is true. With entitlement
already true, it ensures the protagonist's canonical holster exists, resolves
its real wardrobe GUID, enables/unhides it, marks the clothing record in use,
applies the exact metaped component, refreshes ped variation, and restores the
matched dual-wield permission. It does not set an unlock, grant a weapon, write
raw clothing globals or force a UI provider.

The issue log now separates and reads back all four layers:

- progression: named unlock;
- inventory/physical: item count, GUID validity, in-use state, physical metaped
  component, corrected current/default LOADOUT_3 hashes;
- capability: matched allow getter plus primary/secondary attachment-point
  weapon hashes;
- presentation: wheel-open state (the actual dual-provider layout still needs
  visual confirmation because Story exposes no provider-name readback native).

Immediate and 750 ms settled records preserve a failed attempt instead of
calling intent success. The settled record is successful only when the physical
component, inventory in-use state and dual-wield getter all read true. The
three-second heartbeat preserves idle evidence. All native work remains behind
the 250 ms cadence and all mutation remains behind the one-shot latch.

Static checks passed:

```
python tools/reverse-engineering/verify_dual_wield_guard_issue_151.py
PASS #151: recovered the correct LOADOUT_3 addressing and mirrors Rockstar's earned off-hand-holster path with bounded inventory, physical, dual-wield and equipped-weapon readbacks

python -m py_compile tools/reverse-engineering/verify_dual_wield_guard_issue_151.py
PASS

git diff --check -- GameplayTweaks/modules/dual_wield_guard.cpp tools/reverse-engineering/verify_dual_wield_guard_issue_151.py worklog/issues/github-151.md
PASS
```

Integration already has the issue-owned module included and calls
`updateDualWieldGuard(ped, now, mission)` after #130's radial update; no shared
dispatcher change is required. The next integrated build must still be compiled
and installed by the integration owner. Runtime acceptance requires a clean
restart and one continuous log showing the settled inventory/physical/allow
readbacks, then Lexer must see the off-hand holster, see both handgun slots,
draw/fire both equipped handguns, and confirm the state survives save/reload.

## 2026-08-10 recurrence audit before the returned actionable repair

The installed trace disproved the preceding acceptance claim. It recorded the
repair issuing and the inventory record becoming in-use, but the 750 ms settled
readback still had `physical=0`; later heartbeats still had `physical=0`.
Nothing the player can press can repair that failed transition, so the repair
must be automatic and the issue remains actionable.

Two concrete source mistakes caused that false delivery:

- the default expression was changed to
  `1946804 + 57 + 1 + 27 * 11`, but Rockstar's expression is directly
  `Global_1946804.f_57[27 /*11*/]`: the correct address is
  `1946804 + 57 + 27 * 11`. Only `f_1497.f_1[...]` has the extra `+1`;
- the physical application stopped after `_SET_PED_COMPONENT_ENABLED` and
  `_UPDATE_PED_VARIATION`. Rockstar's actual outfit application loop at
  `act_hunting_2.c:50951-50965` calls
  `_SET_ACTIVE_META_PED_COMPONENTS_UPDATED` between those calls. The previous
  repair omitted that required commit step, then reported inventory intent as
  though it could establish a visible holster.

This pass is restricted to that exact Story three-call application sequence,
the corrected default address, and physical/readback diagnostics. It must not
claim success unless `_IS_META_PED_USING_COMPONENT` becomes true and Lexer can
see the second holster and the dual-sidearm wheel after the combined build is
installed.

## 2026-08-10 live eligibility correction

The current installed heartbeat showed `unlock=1`, expected holster count `1`,
valid GUID `1`, `inUse=0`, `physical=0`, `loadout3=0x18`, and `repairs=0`.
The old predicate accepted any nonzero value that did not equal its two known
sentinels. That made an invalid or unowned current component block recovery.

Eligibility now also reads the current component's inventory count and physical
metaped state. Recovery starts when the current value is unowned or when neither
the current nor expected component is physical. A valid alternate owned and
physical off-hand holster remains untouched. The heartbeat records both new
readbacks so another skipped repair cannot be mistaken for execution.

## 2026-08-11 returned repair: remove the shared-inventory mutation

The next clean launch isolated a more serious defect in this issue-owned
repair. Five seconds after startup, #151 edited the off-hand holster inventory
record and metaped state, then its settled readback still reported
`physical=0 missingComponent=1`. Shops remained unavailable in that same
process. This does not prove #151 originally removed the holster, but it proves
the repair itself changed shared inventory state and failed its postcondition.

Before this source change, `fuckups.txt` was read again. The recurring failure
classes were an intent-only setter, a guessed ownership boundary, and a
background inventory fight. The primary sources now used are narrower:

- `act_hunting_2.c:26321-26342` requires an already-earned dual-wield unlock,
  selects the protagonist's canonical off-hand holster, and routes it to
  `MP_COMPONENT_TYPE_LOADOUT_3`;
- `act_hunting_2.c:30179-30185` identifies the published current LOADOUT_3
  record as `Global_1946804.f_1497.f_1[27 /*3*/]`;
- `_downloads/natives.json:74822-74848` resolves `0xD3A7B003ED343FD9` as
  `_APPLY_SHOP_ITEM_TO_PED`. The older SDK/decompiler name
  `_SET_PED_COMPONENT_ENABLED` hid that it applies a shop item.

The replacement does not add, enable, unhide, or mark any clothing inventory
record in use. It requires the named unlock and a positive count of the
canonical holster. After 15 seconds of uninterrupted player-control,
non-mission, non-wheel, non-item-interaction, non-backup-inventory state, it
publishes the exact current LOADOUT_3 value once, applies that already-owned
shop item, commits active metaped components, updates variation, and reads back
the current LOADOUT_3 value, physical component, and matched dual-wield getter.
The one-shot latch remains active after a failed settled result.

Static checks passed:

```
python tools/reverse-engineering/verify_dual_wield_guard_issue_151.py
PASS #151: bounded repair requires an earned, already-owned holster, publishes only Rockstar's exact LOADOUT_3 value, applies the shop item, and makes no inventory-record mutation

python -m py_compile tools/reverse-engineering/verify_dual_wield_guard_issue_151.py
PASS

git diff --check -- GameplayTweaks/modules/dual_wield_guard.cpp tools/reverse-engineering/verify_dual_wield_guard_issue_151.py worklog/issues/github-151.md
PASS
```

Integration must restore the existing module include/call but must not move the
call ahead of the shop-startup protection. Build/install proof is owned by the
integrator. Runtime acceptance remains separate: the settled line must show the
expected LOADOUT_3 hash, `physical=1`, and `allow=1`; Lexer must see the holster
and both sidearm slots, draw/fire both handguns, and retain them after reload.
