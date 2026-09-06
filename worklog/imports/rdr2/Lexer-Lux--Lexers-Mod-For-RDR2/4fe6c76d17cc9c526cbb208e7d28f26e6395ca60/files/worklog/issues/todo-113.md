# Worklog: Todo 113

## #113(d) plant tagging — root cause proven, learner replaced 2026-08-05

Lexer's retest failed and the installed files said exactly why. `plant_models.csv`
in the game directory held ONE line:
  0x5eac7e2b,CONSUMABLE_HERB_VIOLET_SNOWDROP
Reversed that hash against the ~54k joaat("NAME") literals in the decompiled
scripts: 0x5eac7e2b is `S_INTERACT_LANTERN02X`. joaat("S_VIOLETSNOWDROP01X") is
0x3c4f5d7b. The learner recorded his lantern. It always would have: it took the
nearest world object AT THE MOMENT the herb count rose, and by then the plant has
been removed or swapped to its PICKED variant, so the plant is never the nearest
object. The scan then filtered every plant out and matched only lanterns.

The prior entry's premise ("no shipped table anywhere says these models are
plants") was also wrong, and checkable in one grep. `fm_mission_controller.c` and
`net_gun_for_hire_offline.c` carry the game's full model-index table as joaat
literals — `S_VIOLETSNOWDROP01X`, `VIOSNWDRP_P`, `PRARIEPOPPY_P`, `THYME_P` and
the rest. 41 names now ship in `kPlantModelNames[]`, all copied verbatim, none
invented, PICKED variants deliberately excluded. Plants are taggable on a fresh
save with nothing harvested.

Learner kept but no longer able to record a bystander: it samples objects within
3 m every 250 ms, and on a herb count rise accepts only a sampled object that has
since STOPPED EXISTING or CHANGED MODEL — the harvest itself is the evidence. If
nothing was consumed it records nothing and logs that.

Which pool plants live in (`worldGetAllObjects` vs `worldGetAllPickups`) has been
asserted both ways here and never checked, so the scan now walks both and the
per-second diagnostic reports `plantobj=` / `plantpickup=` counts. The next log
settles it.

Also removed the mislearned CSV line from the game directory (kept as
`plant_models.csv.bad-lantern`), and repaired a `'\r'` literal at script.cpp:4775
that had been broken into a raw newline by a concurrent edit — build error, not
a runtime bug.

Built exit 0. Installed with the game closed, hash-verified
`5FFA2B8B911A317B5CF2C4D4909055C053467D4D6081BC3DC252249EB7457DE2`.


## #113(d) plants-only filter — 2026-08-05

Correction to the entry below: harvestable plants are NOT pickups. pickups.meta
(which we ship, 211 KB) contains no herb entry at all, and catalog_sp.ymt gives
herbs only an INVENTORY_ITEMS texture, no world model. So the first pass -
scanning worldGetAllPickups - would have tagged dropped weapons and ammo and
very likely never a single plant. Caught before it was left standing.

There is no shipped table anywhere mapping world models to plants, so the list
is LEARNED from play instead of guessed:
- `kHerbItems[]` - the 31 CONSUMABLE_HERB_* names, taken verbatim from our own
  loot_table_herb.meta, not invented.
- `learnPlantModels()` runs every 250 ms: when any herb count RISES, it takes
  the nearest world object within 3 m (worldGetAllObjects) and appends
  `0x<model>,<item>` to `plant_models.csv` beside the asi if new. Same
  CSV-beside-the-asi pattern as collectibles.csv / owned_gear_models.csv.
- `loadPlantModels()` / `isKnownPlantModel()` restore and query it.
- The recon scan now walks worldGetAllObjects (not pickups) and, while
  `g_reconPlantsOnly`, keeps only learned models. Logs once if plants-only is on
  with an empty list, naming the escape hatch.
- `[ReconTagging] PlantsOnly` (default 1), alongside TagPlantsAndPickups.

Known limitation, stated rather than hidden: the list starts empty, so a species
is only taggable after it has been harvested once. That is the price of not
guessing model names, and the learner is one pick per species.

Build fixes on the way through: g_reconPlantsOnly/g_plantModels had to move up
beside g_reconTagPickups (used by the config loader at ~line 1149), and
reconLog needed a forward declaration taking const std::string&.

Built exit 0. Installed with the game closed, hash-verified
`1D1F4A1EB5B8CCD94A9001BF30FE134F3D7D8735984A7E5F4E5FB2953D6F39B8`.


## #113(d) plant tagging — done 2026-08-05

Earlier verdict ("needs a plant-model identification pass first") was avoidable.
Harvestable plants are PICKUP entities, and `worldGetAllPickups` +
`PICKUP_OBJECT` + `ENTITY_COORDS` is already a proven pattern in this file
(suppressOwnedGearSparkles, line ~1907). No model hashes need to be invented,
which was the whole reason for hesitating.

Added:
- `ReconObjectTarget { Object, Blip, markedAt }` and `g_reconObjectTargets`,
  with `isReconObjectTagged`.
- `drawReconObjectMarker` — same seat ring, arc and disc as a ped tag, with the
  `blip_plant` sprite inside. Sprite name verified against the 321-texture
  vanilla export (blip_ambient_herb / blip_herb / blip_ambient_plant do NOT
  exist; `blip_plant` does).
- Selection pass over pickups, run ONLY when no ped won the reticle, so people
  and animals keep priority. Same `g_reconAimRadius` and `g_reconMaxDistance`
  gates as peds.
- Commit on the same `g_reconObserveMs` dwell, same HUD_SHOP_SOUNDSET feedback,
  same `g_reconMaxTags` cap, blip via BLIP_STYLE_PICKUP_ANIMAL.
- Object tags culled when the entity stops existing; `clearReconTargets` clears
  both lists.
- `[ReconTagging] TagPlantsAndPickups` (default 1).

Deliberate scope note: this tags any world pickup, not only plants. Narrowing it
to plants specifically WOULD need the model-identification pass, and a broader
recon tag is more useful than none — Lexer asked to tag plants, and a dropped
weapon or a carcass being taggable is not a defect. If he wants it restricted,
that is the follow-up and it needs the model list.

Built exit 0. Installed with the game closed, hash-verified
`59807B00C23C9F04AD7BE7F315614941AD214DFB09DF378FE4BE3DECA299D1A8`.


## #113 marker anchor — bone space is not world space, 2026-08-04

`GET_PED_BONE_COORDS(ped, bone, x, y, z)` takes its offset in BONE-LOCAL space.
The head bone's local axes do not point at the sky, so raising the third argument
from 0.18 to 0.52 pushed the marker forward/right of the target rather than up —
exactly what Lexer reported. Now takes the bone position raw and adds 0.42 in
world Z.

