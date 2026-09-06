# github-130 — PICKUP_LEX_CASING fails to create; casings spawn as inert objects

## What the live log actually showed (checked first)

`<game root>\GameplayTweaks.casings.log` is truncated once per launch at
`script.cpp:1770`. At the time of this session it held **two lines**, both from
startup:

```
GameplayTweaks registered; spent casings enabled=1
texture dictionary GENERIC_TEXTURES exists=1 loaded_before_request=1
```

No `create failed` line, and no `spawned casing` line either. That session
simply never ejected a casing, so the live log neither confirms nor refutes the
failure. The `create failed on every ejection` claim in the issue traces to
`worklog/issues/github-11.md:257`, written from an earlier session's log. It is
treated here as a real prior observation, not as something re-verified today.

## Data side: the pickups are correctly registered — this was never the fault

Checked against `MyOverhaul/pickups.meta` (installed live: `lml/MyOverhaul` is a
symlink to `C:\RDR2Mod\MyOverhaul`, declared enabled in `lml/mods.xml`, mapped to
`update:/common/packs/base/data/pickups.meta` by `MyOverhaul/install.xml:71-72`).

- Six pickup types exist, one per caliber, inside `<pickupData>` (which closes at
  line 4080): `PICKUP_LEX_CASING_REVOLVER/PISTOL/REPEATER/RIFLE/VARMINT/SHOTGUN`
  at lines 3895-4050. The code asks for exactly these names
  (`items_casings.cpp:13-18`). There is no bare `PICKUP_LEX_CASING`; that string
  existed only in the log message.
- Every XML field used by the six custom entries also appears in vanilla entries.
  Machine-compared all 141 `CPickupData` items: the set of fields unique to the
  custom entries is **empty**. `CollectionRadiusFirstPerson`, `DarkGlowIntensity`,
  `MPGlowIntensity`, `MPDarkGlowIntensity` are rare (3/135 vanilla) but real;
  `HumanNameHash` appears in 14 vanilla entries.
- Every `PickupFlags` token used is in the vanilla vocabulary:
  `NotLootable` (85), `CollectableOnFoot` (135), `ManualPickUp` (100),
  `RequiresButtonPressToPickup` (100), `RequiresPickingUpAnim` (100).
- Rewards resolve: `REWARD_LEX_CASING_*` (lines 5034-5075) are
  `CPickupRewardAmmo` records with an `AmmoRef` and a `SatchelItem`. That is the
  same shape as all 82 vanilla ammo rewards — e.g. `REWARD_AMMO_TOMAHAWK`
  (`pickups.meta:4388-4394`) carries `<SatchelItem>` too, so the field is not a
  weapon-only field as one might assume from `:3144-3145`.
- Hash casing is **not** the #11 defect here. `joaat()` at `script.cpp:461-464`
  lowercases A-Z before hashing, so the uppercase `PICKUP_LEX_CASING_*` literals
  hash identically to the lowercased names RAGE computes.

Conclusion: `pickups.meta` is not the defect. No data-side change was made.

## Root cause: the code destroyed a pickup that had been placed correctly

`items_casings.cpp` (pre-fix, lines 218-229):

```cpp
pickup = OBJECT::CREATE_PICKUP(pickupType, spawn.x, spawn.y, spawn.z, 0, -1, TRUE, 0, 0, 0.0f, 0);
if (pickup && OBJECT::DOES_PICKUP_EXIST(pickup))
    obj = OBJECT::GET_PICKUP_OBJECT(pickup);
if (!obj || !ENTITY::DOES_ENTITY_EXIST(obj)) {
    log << "PICKUP_LEX_CASING create failed - falling back to plain object\n";
    if (pickup && OBJECT::DOES_PICKUP_EXIST(pickup)) OBJECT::REMOVE_PICKUP(pickup);
    ...
}
```

The failure test is on the pickup's **object**, not on the pickup. A pickup
placement and its physical object are created on different frames:
`CREATE_PICKUP` registers the placement, `CPickupManager` builds the object
afterwards, so `GET_PICKUP_OBJECT` returns 0 at the creation site.

Every Rockstar caller that needs the object polls for it from a **later** update
behind a latch, and not one reads it where the pickup is created:

| creates | reads the object |
|---|---|
| `rcm_crackpot3.c:6077` | `:2318`, inside `if (!bLocal_44)`, latches only once `DOES_ENTITY_EXIST` passes |
| `gang3.c:52146` | `:52929` (`func_1299`), early-returns while the object does not exist |
| `winter1.c` | `:57698`, inside `if (!func_177(iLocal_908, 32))`, sets flag 32 only after the object exists |
| — | `guama2.c:25662`, same `DOES_ENTITY_EXIST` guard |
| — | `braithwaites3.c:54573`, same |

Those are the only four `CREATE_PICKUP` sites in
`_downloads/RDR2-Decompiled-Scripts/script_rel/`
(`braithwaites1.c:63536`, `gang3.c:52146`, `odriscolls3.c:58483`,
`rcm_crackpot3.c:6077`). All four pass `p6 = true` and `modelHash = 0`, matching
our call, so the argument list was never the problem either
(signature: `natives.h:4238`).

So the sequence was: pickup placed correctly → object legitimately not built yet
→ code declares "create failed" → **`REMOVE_PICKUP` deletes the good pickup** →
plain `CREATE_OBJECT` fallback. Deterministic, every ejection, because a
same-frame read can never succeed. The inert object has no reward binding, which
is why the native acquisition card never fired.

The log message was itself a defect (fuckups Class 2): it reported a failure of
the one thing that had not failed, which is why the investigation kept pointing
at pickup registration and `pickups.meta`.

## Changes — `GameplayTweaks/modules/items_casings.cpp` only

Nothing outside this file was touched. No `pickups.meta`, `script.cpp`,
`build.bat`, other module or worklog edits. No new INI keys.

1. **110-159** — new file-local `PendingCasingImpulse` table, the
   `kCasingPickupObjectWaitMs = 3000` reclaim window, `forgetPendingCasingImpulse`,
   `applyCasingEjection` (extracted verbatim from the old inline physics block)
   and `applyPendingCasingImpulse`. The decompiled call sites above are cited in
   the comment.
2. **162** — `deleteCasing` drops any queued impulse for the pickup it removes.
3. **266-304** — the creation branch now separates the two outcomes.
   `!DOES_PICKUP_EXIST(pickup)` is the only genuine failure and still falls back
   to a plain object; a placed pickup whose object is not ready sets
   `objectPending` and is **kept**. The plain-object fallback is now gated on
   `!asPickup` so a pending pickup never gets a duplicate loose object, and the
   `casing object create failed` path now removes the pickup instead of leaking it.
4. **329-344** — rotation and velocity are computed unconditionally; applied
   immediately when the object exists, otherwise parked against the pickup handle
   so the casing still gets the #45 ejection arc a frame or two later.
5. **365-369** — the `spawned casing` line reports `pickup=` and whether the
   object was pending.
6. **663-699** — the update loop adopts the object on the frame it appears,
   releases the parked impulse, and logs the adoption latency. A placement that
   produces no object within 3000 ms is reclaimed with `REMOVE_PICKUP`. This is
   placed **before** the existing "object vanished" check at what is now line 702,
   which would otherwise erase the live pickup — and that branch never called
   `REMOVE_PICKUP`, so it would have leaked it too.
7. **426-449** — 10 s idle heartbeat: `mode`, `world`, `pickups`,
   `awaitingObject`, `queuedImpulses`. Fires on the first update. A casings log
   holding only the two startup lines now proves the module is not running,
   rather than being ambiguous with "nothing was shot" — which is exactly the
   ambiguity that blocked this session from reproducing the reported failure.
8. **260-265** — corrected the stale comment that named a non-existent
   `PICKUP_LEX_CASING` and claimed the object receives physics at creation.

The fix is correct under both readings of the timing question: if the object
*is* available on the creation frame, the code takes it immediately and behaves
exactly as before; if it is not, the pickup survives instead of being destroyed.

**Not built, not installed** — static analysis only this session, per the task
constraints. No compile, no `.asi` copy, no commit, no label change.

## Runtime acceptance (unverified — needs a build + install)

1. Fire one shot. The casings log must show `pickup placed type=0x... object
   pending` followed by `pickup object adopted after N ms ... impulse=1`, and no
   `pickup placement failed` line.
2. If `pickup placement failed` *does* appear, the pickup type genuinely is not
   registered and the investigation moves back to `pickups.meta` — the new
   message distinguishes the two cases, which the old one could not.
3. Walk to the casing: the engine prompt and bend animation must appear (they
   come from the pickup's own `ManualPickUp` /
   `RequiresButtonPressToPickup` / `RequiresPickingUpAnim` flags, so their
   presence is itself proof a real pickup exists).
4. Collect it: the acquisition card must fire, and the log must show
   `casing collected by native pickup`.
5. Confirm the casing still ejects with motion rather than dropping in place —
   that is the deferred-impulse path working.
6. Leave the game idle for 30 s and confirm heartbeat lines accumulate.
