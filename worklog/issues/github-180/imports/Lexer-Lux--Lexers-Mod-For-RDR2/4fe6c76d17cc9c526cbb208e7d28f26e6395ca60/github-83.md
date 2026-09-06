# GitHub #83 - Optional casing-style glint on world cigarette cards

## Implementation

- Added a separate `collectible_effects.cpp` topic module. It attaches
  `scr_generic` / `scr_event_glint` to Rockstar's real streamed cigarette-card
  object and never creates or replaces a card.
- Derived all 144 deterministic card model hashes from the 12 set names and
  card numbers already present in `collectibles.csv`.
- Limited object-pool searches to unretired card placements within 80 metres of
  the player, on a 750 ms interval. The per-frame path only validates effects
  that are already active.
- Tracked World Champions cards 2 and 11 independently. They share one placement
  but have distinct `SPT_02X` and `SPT_11X` model hashes.
- Stopped and removed effects when the option was disabled, its scale changed,
  the map marker was retired, the object was collected/hidden, the object
  streamed out, or an entity handle was reused for another model.
- Kept the controls separate from spent-casing glints. The module reads
  `[CollectibleEffects] CigaretteCardGlintEnabled` (default `0`) and
  `CigaretteCardGlintSize` (default/clamped `1.0`, range `0.05`-`10.0`) directly
  on a two-second hot-reload cadence.

## Integration handoff

- Include `modules/collectible_effects.cpp` after `modules/collectibles_map.cpp`
  in `script.cpp`.
- Call `updateCigaretteCardGlints(ped, now)` every frame. Call it even when no
  valid ped is available so disabling the option or leaving gameplay cleans up
  any active particle handles.
- Add the default-off `[CollectibleEffects]` INI section from GitHub #83.

## Static evidence

- The module contains all 12 catalog-backed model prefixes and validates card
  numbers as 1 through 12 before hashing a model name.
- Discovery is guarded by both an 80 m 2D placement test and a 750 ms timer;
  no all-model search occurs per frame.
- The only entity mutation is starting/stopping a looped particle. It does not
  modify pickup state, prompts, collision, visibility, Eagle Eye, or inventory.
- Full compilation, install/hash verification, and the requested in-game
  subtlety/prompt/Eagle-Eye checks remain integration/runtime gates.

## User-directed removal

The in-game test established that cigarette cards already flash in vanilla and
that this added effect was unnecessary. The module, runtime include/call, and
INI section were removed completely. This is not an effect-tuning retest; the
acceptance check is simply that vanilla card behavior remains and no mod-added
card glint code ships.

Static removal verification confirms that
`GameplayTweaks/modules/collectible_effects.cpp` is absent and that
`script.cpp`, `GameplayTweaks.ini`, and `build.bat` contain no module include,
runtime call, `CigaretteCardGlintEnabled`, `CigaretteCardGlintSize`, or
`[CollectibleEffects]` section. The verifier separately asserts that issue
#32's accepted spent-casing `scr_event_glint` implementation remains intact;
the user-directed #83 removal does not authorize removing casing glints.
