# Worklog: 057 Bandit Challenge Mask Implementation 2026 07 13

## Bandit challenge/mask implementation (2026-07-13)

- Lexer-defined Bandit goals are now written to `goals_sp.meta`: ranks 1–9
  target 50 town hold-ups, 10 fenced wagons, 20 cash registers, 20 ambient
  coach robberies, $500 highest bounty (50000 cents), 25 fenced horses, 50
  stealth kills/knockouts, 500 human kills, and one victim hogtied on train
  tracks. Rank 7 copies Rockstar's proven duplicate-safe stealth sum/binding
  pattern from `goals_sp_missions.meta`. Rank 10 has target zero because the
  linear strand itself guarantees ranks 1–9 were completed.
- `challenges_sp.meta` unlocks these SP assets at ranks 1–3 and 5–9:
  `KIT_MASK_METAL`, `CLOTHING_ITEM_MASK_PIG_001`, `KIT_MASK_BLACK_HOOD`,
  `KIT_MASK_BROWN_SACK`, `CLOTHING_ITEM_SKULLMASK_MR1_002_1`,
  `KIT_MASK_PSYCHO`, `CLOTHING_ITEM_SKULLMASK_MR1_000_1`, and
  `CLOTHING_ITEM_SKULLMASK_MR1_001_1`.
- Explorer is being redesigned as a sequential series of short, deliberate
  exploration/endurance trials awarding exactly one permanent Stamina level per
  rank. Selected ranks so far: 1 Valentine-to-Emerald Station on foot under 7
  minutes; 2 Gill Landing marker to the southern island by swimming; 3 gain and
  fully evade Wanted status on foot; 5 reach the marked Mount Hagen high point;
  9 enter the marked Fort Wallace area and escape on foot without death or
  harming anyone; 10 Saint Denis stagecoach to Colter on foot in under 24
  in-game hours without death/kills while bounty is at least $1,500 separately
  in Ambarino, New Hanover, and Lemoyne. Ranks 4/6/7/8 remain open.
- Explorer challenge markers are temporary script-created map blips plus world
  trigger/marker coordinates shown only when that rank is unlocked and active;
  they are not permanent physical map edits.
- Gambler no longer increases wallet capacity. It governs a Dark Souls-style
  recoverable cash drop: rank 0 drops 100% of carried money on death, every
  completed rank reduces the fraction by 10 percentage points, and rank 10
  drops nothing. Dying again before recovery forfeits the previous drop and
  creates a new one; amount and coordinates must persist safely with a temporary
  recovery marker and no duplication across save/reload.
- GameplayTweaks detects those exact equipped inventory items and implements
  witness suppression chance, fence cash multiplier, low-honor-price immunity,
  bounty-gain scaling, mount stamina recovery, melee/offensive and ranged-
  defense modifiers, bounty-hunter cooldown/flee tasks, and doubled honor loss.
  Completing Bandit rank 10 is detected through the gator gun-belt unlock and
  halves nearby REL_COP/REL_PINKERTONS seeing/hearing ranges by default.
  Values hot-reload from `[BanditMasks]` and `[HonorPrices]`; the latter
  exposes all honor ranks -8..+8 and defaults to mirrored vanilla thresholds
  (+/-2 10%, +/-5 25%, +/-7 50%).
- Rank 4 is not falsely implemented: SP has only
  `CLOTHING_ITEM_GLASSES_NONE`; the desired Outlaw Pass glasses require an
  online-item/meta-ped import. There is a wanted-radius getter but no setter in
  the native DB, so exact equipped search-radius halving still needs a proven
  hook. `Rank4GlassesItem` remains blank until the asset exists.
- 2026-07-13 map-test correction: collectible blips must use a normal vanilla
  coordinate style, valid vanilla sprite names, and one shared display label
  per category so the map Index groups them as `1 of N`. The ten categories
  are cards, bones, rock carvings, dreamcatchers, graves, exotics, legendary
  fish, cabins, treasure-map clues/pickups, and Points of Interest. Individual
  location names must not become 581 separate Index rows.
- `BLIP_RC_COLLECTABLE_*` names belong to the toast/log texture dictionary and
  can render blank when assigned as map sprites. Collectible map markers now use
  only names verified in Rockstar's actual `blips` atlas: newspaper, animal-dead,
  secret, overlay-ring, ambient-death, plant, fishing, home, chest, and POI.
  Train Tracker and Banking likewise use existing vanilla train/bank sprites;
  they are not evidence that arbitrary generated PNGs can be registered as map
  blips. A custom icon still requires a working RDR2 texture-dictionary pipeline.
- Vanilla's map Index layout clips its right arrow when a grouped blip count has
  three digits (144 cards). No MAP native controls that counter/Scaleform width.
  Do not silently split Cigarette Cards after Lexer explicitly requested one
  category; fixing both constraints needs a map-menu UI asset patch.
- Challenge reward editor bug fixed 2026-07-13: `+ reward` used a stale render
  snapshot and alphabetically first vanilla reward (`$15`), so it could overwrite
  a selection made immediately before clicking plus. The required invariant is
  that add appends to the latest edited array without changing any existing row;
  the new row's default is unrelated to that overwrite bug. All reward add,
  remove, and change operations go through one latest-state mutation helper.
  Every rank-10 strand reward was repaired to its full four-piece reinforced set.
  MyOverhaul's reward picker excludes challenge-money enums and the save API
  rejects them, matching the mod-wide no-money-from-challenges decision.
- Existing challenge world-condition scalar fields are editable only through
  vanilla-proven value selectors and show per-field vanilla references. Logical
  AND/NOT nodes remain structural, not fake editable strings. Localization keys
  and goal record IDs are subordinate technical metadata beside/below the field
  they identify, never primary content in the middle of the form.
- TODO #50 is a Dark-Souls-style death bloodstain: outside missions, all cash is
  dropped at one persistent, map-marked, reachable location; a second death
  destroys the prior drop. Placement needs ground/navmesh safety and persistence.
- 2026-07-13 weapon-test correction: loading the OpenIV-exported `weapons.ymt`
  through LML caused handguns to fire only once per draw even though the file
  is byte-identical to the retained vanilla reference. Its active replacement
  is removed from `MyOverhaul/install.xml`; keep weapon data editor-only until
  a runtime-safe serialization/replacement path is proven.
- MyOverhaul was first installed on 2026-07-13 and resynced for explicit testing
  on 2026-07-14. LML data replacements and GameplayTweaks ASI updates require
  a full RDR2 restart to load.
- Challenge names/descriptions in those files are localization keys, not the
  displayed English text. `challenges_sp.meta` contains strand/rank UI keys and
  `goals_sp.meta` contains goal description/toast keys. LEXEDITOR can edit these
  keys and editor-only labels; new prose requires extracting/editing localization
  resources.
- In `loot_items_matrix.meta`, `DamageQuality` is the kill-cleanliness grade
  resolved from weapon/damage rules in `damagecleanlinessdata.meta`; it is
  independent from `SkinQuality`, the animal/pelt grade. Ordinary skin qualities
  are Poor/Good/Perfect (1/2/3 stars), with special Rare and Legendary values.
  LEXEDITOR must render those special values by name, never as zero-star Poor.
- Crime Tweaks 4.0 (saul0097) is copied into gitignored
  `datasets/crimeTweaks` as a read-only `crimeinformation.meta` reference.
- Crime severity is a closed vanilla enum: `None`, `Low`, `Medium`, `High`.
  LEXEDITOR uses a selector and validates it server-side; never expose it as
  free-form text.
- Shop availability is in catalog `shopsinventories`; item prices alone do not
  make an item purchasable. LEXEDITOR's Shops tab edits inventory membership
  and displays existing location/mission/honor/unlock requirements. Newly added
  memberships are unconditional until a requirement editor is implemented.
  In `SHOP SELLS TO YOU`, entering an exact catalog item ID exposes a toolbar
  `ADD TO SHOP` action: a selected shop is added directly, while `All shop
  types` opens a picker containing only shops that do not already list it.
- `loot_items_matrix.meta` is a deterministic animal/quality yield matrix, not
  a probabilistic CLootTableCollection. The UI groups its individual XML yield
  records by DamageQuality + SkinQuality under Loot > Skinning.
- LEXEDITOR consistency rules: every tab shows its source file(s) and has a
  right-side help toggle; only the header SAVE persists mod-file edits. Human
  labels for opaque identifiers are editor metadata in committed
  `editor/labels.json`, not mod data. Applicable tables use reversible,
  highlighted header sorting. Show every available Vanilla/third-party
  reference value, but explicitly state when a dataset/file was never extracted
  rather than inventing a reference.
- Catalog `category` is the precise inventory/catalog classification (often a
  shop/UI slot or subtype); `group` is the broader gameplay family such as
  PROVISION, WEAPON, or CLOTHING used to relate many categories.
- Consumable item-wheel placement is not stored as one explicit radial-slot
  field. The game builds wheel collections from catalog category/type/tag
  filters. Remedy tags distinguish health, stamina, Dead Eye, multi-core, and
  horse items; LEXEDITOR does not yet expose those tags, so category/group
  alone must not be presented as the complete wheel classification.
  Organize the 9 vanilla strands as ranks 1-10. Stat sources/rewards must be
  constrained to vanilla-proven identifiers. Rewards include attribute XP,
  gear unlocks, tutorial/completion events, and vanilla money (removed in mine).
  New strands/rank counts are structurally possible but UI/script/localization
  assumptions are unproven; do not expose creation controls until tested.
- Saving is explicit/manual. Header SAVE is always visible and enables only
  for unsaved edits in the active tab; it is visibly greyed out otherwise.
  Controls never auto-write mod files.
- In-editor links push browser history. Browser Back must restore the previous
  tab and filters instead of leaving the user stranded at the linked record.
- RPF8_TOOL (lazenes/RPF8_TOOL) is explicitly authorized by Lexer as a local,
  external extraction dependency despite its stated reverse-engineered origin.
  Keep all code/binaries gitignored and out of releases. A locally compiled
  read-only CLI can inspect RPF8 archives; CRC-mounted resources require RPFC/
  pfm.dat path resolution rather than direct archive-key guessing.
- Editor workflow decision: Items is the inventory index; Crafting is the
  recipe graph. Item IDs in loot/skinning/crafting navigate to Items, and
  reverse recipe usage navigates to Crafting filtered by ingredient.
- Craft cost keys are not free-form. Vanilla proves COST_CRAFTING, numbered
  variants 2-4, and FIRE/GRILL/KNIFE/TRAPPER/FENCE/PEARSON station variants;
  LEXEDITOR constrains recipes to those values.
- Catalog cash acquire-cost `quantity` is the number of units received per
  purchase, not part of the price. Examples: AMMO_ARROW = 5 for $0.50,
  AMMO_REVOLVER = 60 for $1.00, AMMO_SHOTGUN = 18 for $1.00. LEXEDITOR exposes
  this under Purchase Output with reference values. Container products can add
  a second unpacking layer, so raw acquire quantity is not always the final
  usable-item count.
- `*_AMMOBOX*` catalog records represent physical world/container ammo-box
  props and looting variants (including USED), not separate ballistic ammo
  types. Actual mechanics live on CAmmoInfo AMMO_* records in weapons.ymt;
  pickup rewards map to those real ammo types and grant configured ranges.
- Vanilla American localization was extracted from
  `update_3.rpf/x64/data/lang/american_rel.rpf` with OpenIV into
  `_downloads/extract/localization/update_txt/`. `editor/build_localization.py`
  resolves catalog, challenge, goal, weapon, and ammo keys into
  `editor/vanilla_localization.json`. LEXEDITOR displays those actual in-game
  English strings and saves edits to `MyOverhaul/strings.gxt2`, which LML loads
  as localization overrides. Internal keys remain technical identifiers.
  Missing Rockstar entries must be identified as missing; never present a
  generated/humanized guess as extracted localization.
- TODO #27 is DS3-style overfill storage. Likely implementation is an ASI with
  a custom save-backed stash; RDR2 exposes inventory add/remove/count APIs but
  no general SP storage chest or proven universal rejected-acquisition hook.
- Opaque joaat identifiers can be recovered only by exact candidate hashing,
  known databases, structural comparison, or runtime inference; hashes are not
  reversible. `editor/resolve_hash_labels.py` checks the gitignored
  rollschuh2282/RDR2-Unhashed-Strings corpus. As of 2026-07-12 it resolved 400
  of 1,170 hashed catalog item/effect keys, including 0x0354F6B7 =
  HORSE_EQUIPMENT_MANE_SHORT_009. Never present unresolved guesses as facts.
- Weapon Rebalance standalone 3.2 is stored locally under the gitignored
  `datasets/weaponRebalance` as a read-only schema/value reference. It replaces
  `weapons.ymt`, seven DLC weapon YMTs, and four weaponcomponents files. Do not
  make it writable or ship it.
- Vanilla SP `weapons.ymt` was exported from
  `update_4.rpf/x64/packs/base/data/ai` with OpenIV on 2026-07-12. OpenIV's
  657 hashed schema tags mapped unambiguously by structural comparison with
  the read-only Weapon Rebalance schema; all gameplay values in
  `datasets/vanilla/weapons.ymt` and `MyOverhaul/weapons.ymt` come from the
  vanilla export. Eighteen vanilla-only unknown field names remain hashed and
  are preserved. Parsed inventory: 142 CWeaponInfo and 28 CAmmoInfo records.
  LEXEDITOR Weapons has Weapons/Ammo subtabs, edits every scalar field, and
  displays Vanilla + WR references. MyOverhaul installs it at
  `update:/x64/packs/base/data/ai/weapons.ymt`.
- Weapons/Ammo selectors must show the actual localized label followed by the exact
  internal identifier (for example `Cattleman Revolver —
  WEAPON_REVOLVER_CATTLEMAN`). Records with no vanilla American entry show
  `(no vanilla name)` and remain editable through their localization key.
- Catalog field audit: every item also contains flags, model, priorityaccess,
  tags, satchel size, UI label/description/localization/texture metadata, and
  (in the newer catalog) expiry, besides the fields LEXEDITOR currently edits.
  These are deliberately not flattened into the Items grid: tags and UI data
  are structured links, flags remain largely unhashed, and expiry is identical
  zero/default data. Add graph/selector-aware controls before making them
  writable; never expose them as misleading free-text scalar columns.
- AI editor ownership model requested by Lexer: Profiles/Peds
  (`combatbehaviour` and model/profile mappings), Global (`pedaccuracy`,
  `peddistraction`, damage/noise), Programs & Styles (police/guard/bruiser/
  normal combat directors, melee reasoners, combatstyles). `peddistraction`
  is global; do not misleadingly present it as per-enemy data.
- AI editor implementation: editable, node-preserving scalar/text fields for
  `combatbehaviour.meta`, `pedaccuracy.meta`, `peddistraction.meta`,
  `peddamage.meta`, and `noisetuning.meta`, all copied from vanilla into
  `MyOverhaul/ai` and added to install.xml. Programs & Styles remains read-only
  until there is a graph-aware editor; never flatten decision graphs blindly.
  Use effective update copies/paths for combatbehaviour, pedaccuracy and
  peddistraction; peddamage and noisetuning exist only in common.
- New requested combat/economy work is TODO #22-25: remove auto ammo pickup,
  reduce non-loot payouts, fists KO rather than kill, enemies pick up guns.
  Ultimate Combat Overhaul 1.0.7 (Nexus 5731) is the reference for #24/#25;
  selected files are local under gitignored `datasets/uco`. Its manifest
  replaces blips, weapons, special abilities, hit reactions, crime, accuracy,
  peddamageinfo, combatbehaviour, pedhealth, damages, two combat programs and
  a natural-motion blend file, plus an ASI. Enemy gun pickup is explicitly
  data-driven by per-profile `MaxWeaponPickupDistance` and
  `WeaponPickupChance` in combatbehaviour.meta; UCO values are exposed inline
  in the AI editor as read-only references.
- UCO's nonlethal-fists data mechanism spans `damages.meta` (unarmed action
  damage plus `DRA_KNOCKOUT`) and `pedhealth.meta` (per-profile
  KnockedOutHealthThreshold, KnockedOutHealthToRecover, KnockedOutCount). Its
  ASI may still enforce nonlethality/recovery/crowd logic; do not assume the
  two data files alone reproduce the whole feature until tested.
- TODO #26: reduce harvestable plant spawn rate. `loot_table_herb.meta` only
  changes yields. Current candidates (`loot_table_herb_passthrough`, wb_herbs
  scenarios, lootable_herbs, vegetation modifiers) do not establish a global
  plant-density control; research an existing spawn-rate mod first.

