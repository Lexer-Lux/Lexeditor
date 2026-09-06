# GitHub issue #85 — compendium discovery glint probe

## Requested behavior

Glint anything in the world that can be entered in the compendium but has not
yet been discovered: animals, fish, herbs/plants, horses, weapons, and
equipment. The current live issue explicitly requests a probe first and a
concrete procedure for supplying the missing runtime evidence.

## Evidence and diagnosis

- The current native database exposes the read-only
  `COMPENDIUM_WAS_ANIMAL_OBSERVED(Ped)` (`0x23B5E9C5160BC04F`). The earlier
  issue comment that no animal getter was exposed is therefore stale.
- Rockstar Story Mode scripts use
  `_COMPENDIUM_GET_NUM_OF_ENTRIES_IN_CATEGORY` (`0x729D52F61A5A9E22`) with the
  exact categories `ANIMALS`, `FISH`, `HERBS`, `HORSES`, `WEAPONS`, and
  `EQUIPMENT`. That is a category-wide discovered count, not proof of any
  individual world target's state.
- No documented equivalent of `COMPENDIUM_WAS_ANIMAL_OBSERVED` was found for a
  particular herb, horse breed, weapon, or equipment entry. Implementing
  non-animal glints from category totals would knowingly produce false glints.

## Implemented probe

- Added a disabled-by-default, F10-triggered, read-only module that writes
  `GameplayTweaks.compendium-probe.log`.
- Each capture records all six category totals, the aimed entity's model and
  discoverable name/type hashes, unlock visibility/readback candidates, the
  player's equipped weapon hashes across relevant slots, and up to 24 nearby
  nonhuman peds.
- Ped records include animal type, short description, animal-observed result,
  horse classification, category/subcategory/entry candidates, and distance.
- The probe never calls compendium observation/discovery setters, herb-picked
  setters, or unlock setters, so measuring a target cannot discover it.

## Exact in-game procedure

After the integration owner registers the module, merges the INI fragment,
builds, and installs it:

1. Set `[CompendiumGlintProbe] Enabled=1` and fully restart Story Mode.
2. Aim directly at a **Known observed animal** and tap F10 once. A short UI
   select sound confirms the capture.
3. Aim directly at a **Known unobserved animal** of another species and tap F10.
4. Repeat once for a known observed horse and once for a breed not yet observed.
5. Aim at an unpicked herb/plant and tap F10, pick it, then aim at another live
   instance of the same plant and tap F10 again.
6. Equip a weapon already present in the compendium and tap F10; then equip or
   inspect a weapon/equipment item absent from the compendium and tap F10.
7. Send `GameplayTweaks.compendium-probe.log`. Capture numbers preserve this
   order, so no manual log editing or technical annotation is required.
8. Return `Enabled=0` after capture.

## Evidence boundary

Static evidence now establishes an exact animal readback and a safe probe for
all requested categories. It does not establish the per-entry predicates for
plants, horses, weapons, or equipment, and no glint effect has been implemented
or claimed. The issue remains actionable until the probe is integrated,
installed, and its comparison log is decoded into reliable predicates; only
then can the player-visible glints be implemented and moved to in-game testing.

## Integration handoff

- Include `modules/compendium_glint_probe.cpp` in the shared translation unit.
- Call `loadCompendiumGlintProbeConfig()` from the shared INI loader.
- Call `initializeCompendiumGlintProbe()` once after paths/config are ready.
- Call `updateCompendiumGlintProbe(playerPed, blocked)` each frame.
- Merge `ini-fragments/github-85.ini` into the shipped INI.
- Build/install/hash-verify through the release manifest. Do not move #85 to
  `test me`: the installed probe still requires the comparison run before the
  requested glint feature exists.
