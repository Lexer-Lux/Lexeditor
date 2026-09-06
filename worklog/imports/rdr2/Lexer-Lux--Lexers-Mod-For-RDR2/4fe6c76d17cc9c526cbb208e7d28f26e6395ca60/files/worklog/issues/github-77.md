# GitHub #77 — removing a mask leaves its check mark on

## Requirement

Removing the carried mask through the radial must clear the carrier item's
check mark. Putting the mask on must still set it, and later wardrobe/script
changes must still be reflected after the interaction settles.

## Cause

`updateCarriedMask` combined the physical component scan with a remembered
toggle latch. The previous repair stopped a positive scan from re-arming the
latch only while `ITEM_INTERACTION_RUNNING` was true or during a fixed
four-second window. Rockstar's `bandana` script also uses a four-second failure
deadline and applies clothing changes at an animation event, so elapsed time is
not proof that the component global already reflects the requested state.

If the old face component was still readable after our window, the code copied
that stale `worn` state back into the latch. Every later update then passed true
to `INVENTORY_SET_CLOTHING_ACTIVE`, leaving the radial check mark on.

Evidence:

- `_downloads/RDR2-Decompiled-Scripts/script_rel/bandana.c` changes the outfit at
  an animation event and has a 4000 ms failure path; it does not promise that a
  component-global transition coincides with our redirect frame.
- `codex/inventory-radial.md` establishes that the custom carrier's
  clothing-active state drives the ordinary clothing-slot presentation.
- The installed log showed the carrier starting settled and unchecked; it did
  not contain a later redirected interaction, so it could not disprove the
  reported removal path.

## Change

`GameplayTweaks/modules/items_casings.cpp` now records the exact state requested
when it redirects the carrier interaction: worn for MASK/BANDANA ON, removed for
MASK/BANDANA OFF. While that command is pending, the requested state is the
authoritative argument to `INVENTORY_SET_CLOTHING_ACTIVE`; a stale pre-transition
component cannot reverse it. The command is released only after the item
interaction has ended and the physical scan agrees. Once released, ordinary
wardrobe or script changes are mirrored directly from the scan. Choosing a
different carried mask also cancels a pending state belonging to the old item.

The transition log now includes `pending=-1|0|1` beside scan/latch state.

## Static verification

- The removal redirect assigns pending state `0` before starting MASK_OFF.
- The put-on redirect assigns pending state `1` before starting MASK_ON.
- Pending state, rather than `scan || latch`, controls clothing-active state.
- Pending state clears only after the interaction ends and scan equals the
  requested state.
- No dispatcher, INI, generated index, build, install, GitHub, or shared editor
  file was changed by this issue agent.

## Integration and in-game acceptance

The integration agent should rebuild the generated knowledge indexes, perform
the single full GameplayTweaks build/install/hash verification, then move #77
from `actionable` to `test me`.

In game, equip the carried mask from the regular item wheel, confirm its check
mark appears, then remove it from the same segment and confirm the mark clears.
Repeat once while holding a rifle, and confirm that changing the carried mask at
a wardrobe still updates both the carrier and its check mark.

## Second live failure correction

The next installed log established a stronger fact: it recorded the carrier as
`worn=0` and `scan=0`, yet the user still saw the check mark. The requested-state
latch was therefore no longer the remaining defect. The inventory in-use native
had the correct false value, but the item wheel had never been told to rebuild
its cached presentation: refresh bits 8 and 16 were set only when the carrier
item/cache changed, not when its in-use state changed.

The carrier now raises the same 8|16 wheel refresh whenever its applied worn
state changes, including the first unchecked synchronization after startup.
This directly couples the false inventory state to a refreshed radial instead
of trusting an already-rendered check mark to notice the native mutation.

## Horse weapon-wheel crash guard

Runtime logs from an `ERROR:FFFFFFFF` raised while taking a gun from the horse
ended with the weapon wheel selecting a repeater and the clothing availability
bit dropping from 1 to 0. `updateCarriedMask` mirrored that transient wheel-owned
state back into the same live inventory transaction with
`INVENTORY_DISABLE_ITEM`, clothing-active, and carried-clothing cache writes.

Carrier synchronization is now completely deferred while
`INPUT_OPEN_WHEEL_MENU` is held and for two seconds after the wheel closes. The
guard runs before inventory, clothing-state, equipped-bit, or clothing-cache
reads and writes, so Rockstar can finish the horse weapon equip transaction
without concurrent carrier mutation. The log records
`weapon-wheel: carrier sync deferred` once per deferral interval.

This is built/static evidence only until the installed build survives the same
horse weapon retrieval in game.

The first guard covered only carried-mask synchronization. A later horse-rifle
crash proved that `updateSharedAmmoCaps` was still calling
`SET_MAX_AMMO_OVERRIDE` for enabled ammo families every 250 ms during the same
Rockstar weapon-transfer transaction. The wheel guard is now shared: carried
mask synchronization plus shared ammo/item-cap reads and writes all pause while
the wheel is open and for two seconds after it closes. Build
`B91987788C09D508BAEFB88E0E0223D8B599EF7785B169B963E6F38F0573B271`
was installed and hash-verified; repeating horse weapon retrieval remains the
runtime acceptance check.

## Third live failure — "the animation plays but the mask never goes on"

Reported 2026-08-06 18:14: selecting the carried mask from the radial plays the
put-on animation, but no mask appears and no check mark appears. This is a
REGRESSION, not the original check-mark defect: before the wheel guard landed,
the mask itself went on and only the check mark misbehaved.

### Root cause

The horse-weapon-wheel transaction guard was placed at the TOP of
`updateCarriedMask`, so it returned before the proxy redirect.

The redirect is the one part of this feature that has to run inside exactly the
window the guard blocks. Rockstar's `BANDANA` script is started with the item as
a script parameter — `bandana.c:6-24` copies `ScriptParam_0.f_2` into
`Local_0.f_1` — and at anim event `822176400` it applies the clothing for THAT
item (`bandana.c:88-101`: `func_11` when `func_10(item) == 81053684`, else
`func_12`). Our radial segment is a proxy catalog item with no mask component,
so unless the interaction is torn down and restarted on the real record before
that anim event, the player gets the animation and nothing else. The carrier
interaction begins the instant the radial closes, i.e. inside
`INPUT_OPEN_WHEEL_MENU held + 2000 ms`, which is precisely what the guard
covered.

Runtime proof from the installed build's
`GameplayTweaks.carried-mask.log` (game root, session truncated at launch):

- five `weapon-wheel: carrier sync deferred` lines,
- one startup `worn=0 scan=0 latch=0 pending=-1 ... selectedRoute=4` line,
- and ZERO `proxy-redirect` lines for the whole session.

The redirect did not fire once, which is consistent with the reported symptom
and inconsistent with any theory that only concerns the check-mark state.

### Change

`GameplayTweaks/modules/items_casings.cpp` only.

1. The wheel guard is moved out of the top of `updateCarriedMask` and placed
   immediately before the 500 ms apply block, so it still wraps every mutation
   it was added for — `INVENTORY_ADD_CLOTHING`, `INVENTORY_REMOVE`,
   `INVENTORY_ENABLE_ITEM` / `INVENTORY_DISABLE_ITEM`, `INVENTORY_SET_HIDDEN`,
   `INVENTORY_SET_CLOTHING_ACTIVE` and the carried-clothing cache global writes
   — while the read-only component scan and the proxy redirect run again. Its
   line is now `weapon-wheel: carrier mutation deferred` so a log from the new
   build is distinguishable from the old one. The redirect only fires when the
   RUNNING item interaction is our own carrier proxy, which cannot be Rockstar's
   horse-weapon equip transaction, and it manipulates tasks rather than
   inventory records.
2. Instrumentation that can observe its own failure. Every change of the running
   item-interaction item now logs
   `interaction=0x… desiredProxy=0x… redirectedProxy=0x… wheelGuard=0|1`, so a
   carrier use that does not redirect is visible as an `interaction=` line
   carrying our proxy hash with no `proxy-redirect` line after it. A 30 s
   `heartbeat` line records selectedRoute / usingMask / maskOnFace / pending /
   radialAvailable / wheelGuard, so a silent log proves `updateCarriedMask` is
   not running rather than "nothing happened". The log is still truncated once
   per launch at the existing `session-start` line.

Nothing else in `items_casings.cpp` was touched; no INI key was added or
changed; `script.cpp` (which owns `weaponWheelTransactionBusy` and the shared
ammo-cap guard) was not modified, so the ammo-cap half of the crash guard is
unchanged.

### Not done

- No build, link, install or hash. Static change only; the integrator builds.
- The original check-mark defect is NOT independently re-diagnosed here. With
  the redirect dead, `pendingMaskWornState` was never set and no `worn=1`
  transition existed to test, so any further check-mark theory would have been
  a guess. Judge it again from the first log that contains `proxy-redirect`
  lines and their following `worn=`/`interaction=` lines.

## Current actionable pass

The proxy redirect now writes the carrier's clothing-active state immediately
from the commanded worn state and raises the wardrobe refresh bits before the
real mask interaction. This removes the two-second wheel-settle window that
left the proxy checked after the mask was already equipped. The broad horse-
weapon transaction guard remains unchanged. The issue verifier passes; runtime
acceptance must still confirm checkmark, worn state, and horse-wheel stability.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-10 second-selection correction

The unified trace proved the check mark was not merely stale. Two consecutive
proxy selections both logged `worn=0 carrierCommand=1`; the physical component
scan remained false after the first real MASK_ON interaction, so the second
selection issued MASK_ON again. MASK_OFF was never requested and the check
mark could not clear.

The commanded pending carrier state is now authoritative when choosing the
next interaction. If the first selection commanded worn=1, the second sees
worn=true even while the component scan is still stale, issues MASK_OFF, sets
pending=0, and immediately clears the carrier check mark. Once a physical scan
reaches the commanded state, the existing settlement path resumes ownership.

## 2026-08-11 shared-cache safety correction

The accepted check-mark implementation also contained an unsafe raw clothing-
cache writer. It treated `1946804 + 2658` as the cache base, but Story proves
the structure starts at `Global_1946804.f_2657`; it also used the bandana count
where masks require `.f_22` and omitted the complete auxiliary/cache-copy
transaction. The installed log proved that this wrong startup write executed
immediately before the continuing shop regression.

All direct writes to `Global_1946804` and its refresh flags were removed from
the carried-mask updater. The already accepted interaction and commanded-state
logic remain, using only Rockstar's inventory GUID, availability, hidden, and
in-use natives. Runtime must confirm that the radial check mark still follows
MASK_ON/MASK_OFF after this safety correction; no source or native readback can
replace that visible check.
