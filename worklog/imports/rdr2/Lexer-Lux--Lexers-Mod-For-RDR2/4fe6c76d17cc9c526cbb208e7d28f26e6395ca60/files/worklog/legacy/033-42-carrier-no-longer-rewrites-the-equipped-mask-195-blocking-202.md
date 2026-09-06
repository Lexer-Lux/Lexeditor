# Worklog: 033 42 Carrier No Longer Rewrites The Equipped Mask 195 Blocking 202

## #42 carrier no longer rewrites the equipped mask + #195 blocking — 2026-08-04

Build `FCBC529C0AE3BE3B9AFAA624CD5474B84904261E88CBDFB03FBCEED15A204EFC`,
installed and hash-verified, INI synced. Full restart required.

- #42 ROOT CAUSE (save-state damaging). `updateCarriedMask` decided "Lexer picked
  a new mask at a wardrobe" from `equippedBits & ~previousEquippedBits`. But
  wearing the carried mask calls `START_ITEM_INTERACTION(..., desiredReal,
  MASK_ON_*)`, which equips that real record and makes its bit RISE. The
  carrier's own action therefore fed straight back into its own selection
  detector. Compounding it, the rising scan took the LOWEST-INDEX set bit rather
  than the route actually equipped, so with routes ordered
  BLACK_HOOD/BROWN_SACK/GREY_CLOTH/METAL/PSYCHO/PIG/SKULL_0..2, selecting Psycho
  (4) could hand the carrier to any lower-index mask that rose alongside it.
  Reported as "showed Psycho, selected it, it became the Executioner Hood — and
  actually changed my equipped mask to it."
  Fix: new `maskSelfEquipUntil` window (4 s) set at `START_ITEM_INTERACTION`;
  rising bits are ignored entirely while it is live or while
  `ITEM_INTERACTION_RUNNING`; and a rise on the route we already carry is never
  treated as a new selection.
  NOT FIXED: the stuck check mark and the missing camp/animation greying.
  `INVENTORY_SET_CLOTHING_ACTIVE` is fed `wornRoute == selectedRoute`, and
  `wornRoute` is derived by scanning 39 component slots for the mask record —
  which very likely reports true whenever the record occupies a slot, worn or
  not. Needs a real "is it on his face" test plus disabled-state gating; do not
  guess at it blind.
- #195: `[Prone] BlockWeaponActions=1` (new) disables INPUT_OPEN_WHEEL_MENU,
  INPUT_OPEN_SATCHEL_MENU, INPUT_SELECT_WEAPON, INPUT_RELOAD,
  INPUT_SELECT_NEXT/PREV_WEAPON and INPUT_HOLSTER_WEAPON across all three groups
  every frame while prone. `BinocularMode` default changed 1 -> 0 (refuse).
  AIM and ATTACK are deliberately NOT blocked: they do nothing prone today, and
  disabling them also kills the head tracking that shows the aim state is live.

