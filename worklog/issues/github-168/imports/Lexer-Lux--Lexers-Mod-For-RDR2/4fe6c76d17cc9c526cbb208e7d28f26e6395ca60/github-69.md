# GitHub #69 — No sparkle on owned gear

## Requested behavior and existing state

Owned weapon pickups should stop glowing when the player already owns that
weapon. The issue's separate collectible-hat path still requires the existing
human-controlled identification session, so its `needs a human` workflow state
was preserved.

## 2026-08-09 delayed-abort repair

Progressive crash isolation proved that the weapon sparkle controller caused
Rockstar's delayed `ERROR:FFFFFFFF`: Ancient Tomahawk and Hunter Hatchet each
survived separate three-second windows, and the error began only after
`suppressOwnedGearSparkles` activated.

The controller correctly used SDK natives
`SET_PICKUP_PARTICLE_FX_HIGHLIGHT` (`0x1607C7D9B3021DF5`) on the pickup placement
and `_SET_PICKUP_OBJECT_GLOW_ENABLED` (`0x7DFB49BCDB73089A`) on its object. It
then issued undocumented hash `0x50C14328119E1DD1` through a locally invented
`BLOCK_PICKUP_LIGHT` name and passed an object handle. The SDK identifies the
actual `BLOCK_PICKUP_PLACEMENT_LIGHT` as different hash
`0x0552AA3FFC5B87AA`; there was no evidence that the shipped third call accepted
that object or controlled a pickup light.

The fabricated third mutation was deleted. The two documented visible-effect
setters remain, guarded by `DOES_PICKUP_EXIST` and `DOES_ENTITY_EXIST`, and the
unified log now records each newly suppressed pickup, object, model and owned
item. `verify_owned_gear_sparkle_crash_repair.py` passed.

Full development ASI
`20606EB185A06CB52AF979EFAEB8021F94E42ADC8B94172F7EFAF3CB8CA6BB6B`
was installed with the complete, non-bisect update pipeline. Source/game-root
hashes matched. Runtime acceptance remained pending; no labels were changed.

## 2026-08-09 failed first repair and pickup-pool removal

The first repaired full build failed immediately after its five-second startup
quarantine. Its unified log contained no `owned-gear-sparkles` suppression
record, proving that no configured owned pickup matched and neither surviving
effect setter ran before Rockstar raised `ERROR:FFFFFFFF`. That disproved the
claim that undocumented hash `0x50C14328119E1DD1` was the exact cause; the
three-way staging only proved the old controller's activation window.

The replacement no longer enumerates, resolves, or mutates pickup placements.
It enumerates loaded world objects, rejects attached weapon props, matches only
configured owned-gear models, and applies the SDK object-typed
`_SET_PICKUP_OBJECT_GLOW_ENABLED` operation. The verifier requires that the
controller contain no `worldGetAllPickups`, `PICKUP_OBJECT`, or
`SET_PICKUP_PARTICLE_FX_HIGHLIGHT` path. Runtime acceptance remains pending and
the issue's existing `needs a human` label remains unchanged.

The first object-pool replacement build `0F2BD482...` also failed about two
seconds after the update pipeline released. It rejected attached objects but
did not prove that each remaining weapon-model object was a pickup before
calling the pickup-object-only glow native. The SDK provides that exact type
guard as `OBJECT::IS_OBJECT_A_PICKUP`; the controller now requires it before
any ownership query or glow mutation.

## 2026-08-09 conclusive continuation result

The shortened continuation build survived the repaired Ancient Tomahawk path
and Hunter Hatchet. It raised `ERROR:FFFFFFFF` only after
`owned-gear-sparkles` activated and while child vulnerability remained held.
The object scanner already required `DOES_ENTITY_EXIST`, rejected attached
objects, and required `IS_OBJECT_A_PICKUP`; it still failed before recording a
matched suppression.

The weapon sparkle implementation is therefore removed from the live
translation unit rather than left behind as a hidden switch. The loader, timer,
pool scanners, highlight/glow wrappers, and dispatcher call are absent. This
restores the rest of GameplayTweaks without claiming #69's weapon behavior was
fixed. The issue's existing `needs a human` state is preserved because its
separate collectible-hat identity session is still outstanding; no label was
changed by this crash repair.
