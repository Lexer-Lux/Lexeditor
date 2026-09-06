# GitHub #30 — Bloodborne/DS2-style tonic refilling

## 2026-08-11 blocked-runtime correction

The prior implementation violated the issue relationship. GitHub records #30
as blocked by open exploratory #26, DS3-Style Overflow Storage. The isolated
tonic module nevertheless shipped its own reserve, camp detector, and inventory
mutation path before the shared storage system or its campsite inventory UI
existed.

The broken shop session proved that this partial feature executed when it must
not have executed. An inactive saved campsite had no physical camp and no
tracked thread, but `player_camp` still had one live reference. Two seconds
later the tonic module logged `refill-trigger reason=camp` and entered its
inventory path. This was not a valid rest action and did not use the blocked
shared storage feature.

The integration therefore removed `tonic_refill.cpp` from `script.cpp`, removed
its update call, and removed the `[TonicRefill]` INI/editor surface. The source
file remains only as rejected attempt history; it is not compiled or executed.
#30 stays open and blocked by #26. It is not test-ready or actionable until
Lexer chooses to implement #26 after its exploratory decision.

## 2026-08-06 implementation

The live requirement is a shared active allotment for each of the three player
tonic families, not a separate full stack for every strength:

- Health Cure: weak, standard, potent, special.
- Bitters: weak, standard, potent, special.
- Snake Oil: weak, standard, potent, special.

Amounts above a family's active capacity go to persistent mod-owned storage.
Entering camp and completing the death sequence refill each family's empty
active slots from that storage, special first and weak last. If storage cannot
fill every empty slot, one feed message reports the exact Health, Stamina, and
Dead Eye shortfall.

`GameplayTweaks/modules/tonic_refill.cpp` implements the feature as an isolated
module. It polls the twelve real catalog items, recognizes positive inventory
deltas, and moves only the newly acquired tier into storage when possible. This
matters when the active allotment is already full: picking up a special tonic
stores that special tonic instead of evicting an unrelated weak bottle. An old
save that begins above the new cap is normalized once, weakest first, so the
strongest bottles remain active.

Every inventory mutation is verified by the before/after count. Reserve is
increased only by an observed removal and decreased only by an observed add.
Each verified mutation is written immediately to
`GameplayTweaks.tonic-storage.ini`; return values alone are not treated as
proof. `GameplayTweaks.tonic-refill.log` records overflow, refill order, totals,
and triggers.

The catalog's `SLOTID_SATCHEL` quantity was raised from 3 to 999 only for the
twelve managed tonic records. That is the prerequisite found by #26: the game
must first accept the acquisition so the ASI can observe its delta and divert
the excess. The low player-visible family cap is enforced by the module.

Base capacities are INI-driven (`HealthCapacity`, `StaminaCapacity`, and
`DeadEyeCapacity`, default 3). The currently completed Master Hunter rank adds
to Health capacity, Naturalist/Herbalist adds to Stamina, and Weapons Expert
adds to Dead Eye. Those are not invented associations: their shipped challenge
headers explicitly say that those strands increase those three tonic
capacities, and all live goal hashes were read from `challenges_sp.meta`.
`upgradeTonicCapacity(family, amount)` additionally persists an explicit bonus
for future non-challenge rewards through one authoritative path.

Camp entry is a rising edge of Rockstar's player/gang camp scripts or proximity
to one of the mod's activated campsites. Death uses the existing
`deathSequenceEnded` edge and waits 1.5 seconds so Rockstar can finish restoring
the inventory before the refill mutates it.

## Integration boundary

This pass did not edit `script.cpp`, build, install, change GitHub labels,
commit, or push. The integration agent must:

1. Include `modules/tonic_refill.cpp` after `modules/world_economy.cpp` so the
   module can read activated campsite state.
2. Call `updateTonicRefilling(ped, now, deathSequenceEnded)` once per main-loop
   frame after `deathSequenceEnded` is computed.
3. Add the following documented defaults to the shipped INI:
   `Enabled=1`, `HealthCapacity=3`, `StaminaCapacity=3`, and
   `DeadEyeCapacity=3` under `[TonicRefill]`.
4. Run the full build/static suite, install the ASI, INI, and changed catalog,
   and hash-check the installed copies.

## Runtime acceptance

1. With Health capacity 3 and three active Health Cures, acquire weak and
   special Health Cures separately. Each new item must leave the active total
   at 3, increase its matching persistent tier, and show the storage feed.
2. Spend two active Health tonics, enter camp, and verify special refills before
   weak. Repeat across a restart to prove reserve persistence.
3. Spend more tonics than storage can replace, enter camp, and verify the feed
   reports the exact remaining shortfall once.
4. Repeat the refill on death and confirm it happens after respawn inventory is
   available, not during the death camera.
5. Repeat one overflow/refill cycle for Bitters and Snake Oil.
6. Complete the next Master Hunter, Naturalist, or Weapons Expert rank; verify
   only its associated active capacity grows by one. Also verify an explicit
   `upgradeTonicCapacity` bonus survives a restart.
