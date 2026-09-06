# Worklog: 059 Editor Taxonomy And Shop Ux 2026 07 12

## Editor taxonomy and shop UX (2026-07-12)

- Rockstar's `CI_CATEGORY_HERBS` contains only 7 records and is not a
  player-facing list of plants. LEXEDITOR therefore provides a derived
  **Plants** filter using direct `loot_table_herb.meta` sources plus
  `CONSUMABLE_HERB_*`; direct `Collectible` entries count as catalog sources
  (not only `Type=Item`) so the 13 orchids are included. The result is all 46
  collectible plants while preserving Rockstar's raw category in each row.
- Shops uses one shop-type selector rather than one card per inventory. "Shop
  sells to you" edits `shopsinventories`, catalog acquire-cost purchase yield,
  and catalog buy price. "You sell" edits generic `SELL_SHOP_DEFAULT` payout/sellability.
  Merchant buy-interest remains a separate, not-yet-mapped category/script
  filter and the UI must never imply that assigning a sell price makes every
  selected merchant accept the item.
- Shops render regression fixed 2026-07-12: table code must use the defined
  `cashParts(costs, section)` extractor; an accidental call to nonexistent
  `moneyParts()` left both modes blank after drawing only the toolbar. Keep the
  shop selector enabled in both modes, even though sell-side acceptance is not
  yet mapped.
- Items buy/sell price cells use `⌕` navigation when a cash price exists: buy
  opens Shops filtered to the item and lists every `shopsinventories` seller;
  sell opens the resale view but must state that merchant buy-interest remains
  unmapped. `+` on an N/A buy price now creates `COST_SHOP_DEFAULT`; `+` on
  sell creates `SELL_SHOP_DEFAULT`. Price and inventory membership are separate.
- No-price WEAPON_MOD does not mean dummied out. Of 212 current component
  records, 96 lack a buy cost and 73 of those are already listed in
  `ST_WEAPON_MOD_STORE`, commonly free/default parts. Example: M1899 narrow
  sight and short barrel are equipped defaults; wide sight is $5 and long
  barrel $12. The 23 no-price/unlisted records mix plausible unused cosmetics
  with internal clips, straps, and ammo-mode components; classify individually
  before adding a price/shop membership.
- Weapon component benefit layers are separate. Catalog WEAPON_MOD items can
  reference effect `0x28C28678` (raw 5 / applied 5%), shared by improved sights
  and long barrels and likely used as item/stat-card benefit metadata. Real
  mechanics are in `weaponcomponents.meta`: e.g. Cattleman wide sight has
  `CameraFovModifier=0.95` while its long barrel has `AccuracyModifier=1.10`.
  Editing the catalog effect is not proven to alter either mechanical field;
  never auto-link them. TODO Testing now explicitly checks whether the edited
  improved-sight catalog effect is noticeable before claiming the feature.
- Craft recipe IDs are never arbitrary text: inline Items and the Crafting tab
  validate ingredient IDs against existing catalog keys and Learned against
  existing vanilla-derived recipe unlock IDs (plus ALWAYS KNOWN), with a
  searchable picker. Inline recipe headers keep `Makes N` as one unbreakable
  phrase so the neighboring Used-in-Recipes value cannot read as its yield.
- Ingredient and Learned controls are read-only ID displays plus searchable
  pickers, not editable text boxes. Header SAVE is global: its enabled state
  and count cover edits across every tab, and clicking it saves every dirty
  subsystem rather than whichever tab happens to be visible.
- The Items plant filter intentionally combines 46 collectible plant records
  split by Rockstar across several technical catalog categories: 33
  `CONSUMABLE_HERB_*` herbs/berries/mushrooms and 13
  `PROVISION_RO_FLOWER_*` orchids. Never present `CI_CATEGORY_HERBS` alone as
  the user-facing Herbs category; it contains only seven records.
- Craft cost keys are recipe context/variant identifiers. `COST_CRAFTING_2`
  through `_4` are alternate ingredient formulas for the same output, not
  separate stations. FIRE covers tonics/remedies/coffee, GRILL seasoned meat,
  KNIFE plain-meat cooking, and TRAPPER/FENCE/PEARSON identify NPC contexts.
- Crafting supports sortable Output, context/variant, Yield, Ingredients, and
  Learned columns. The Items recipe column links to Crafting with an exact
  output filter; ingredient reverse usage remains a separate exact filter.
- Vanilla already tracks stealth kills with stats (`BaseId=KILLS`,
  `PermutationId=STEALTH`) and stealth knockouts similarly. Mission goals also
  combine UNAWARE kills while avoiding double counting. Prefer exposing these
  existing stat/permutation sources in the challenge editor before building a
  script-side counter. Truly unregistered events require a custom ASI/save and
  cannot be assumed to integrate directly into the vanilla StatsGoal UI.
- Challenge score-source choices must preserve complete `(BaseId,
  PermutationId)` pairs. The old flattened dropdown made `STEALTH` impossible
  to select. LEXEDITOR now exposes vanilla-proven `KILLS + STEALTH`,
  `KNOCKOUTS + STEALTH`, and `KILLS + UNAWARE` pairs and can create a missing
  `PermutationId` element when applying one to an existing stat requirement.
- `KILLED + AT_BAT` means bats killed (`AT_` denotes an animal-type
  permutation). Vanilla uses it as a binding/exclusion counter in Sharpshooter
  flying-bird goals so a flying bat does not count as a flying bird.
- Challenge requirements are nested logic trees, not flat lists. Preserve and
  display each desiredGoal node's role: primary `scoreParam` counts toward the
  goal; a `bindParam` with `CHECK_FOR_SCORE_WHEN_BIND_NOT_PROGRESS` is an
  exclusion guard; other binding params are required conditions/triggers.
- Challenge cards must also expose non-stat `CAICondition*` nodes. For example,
  Sharpshooter rank 3 is gated by `CAIConditionGoalContext` /
  `CHAL_CTX_ON_MOVING_TRAIN`; the word `Train` in the goal's internal name has
  no mechanical effect. These conditions were previously omitted from the UI.
- Tab explanations must never be inserted as permanently visible info boxes.
  Put them in `TAB_CONTEXT.help`; the right-side `?` is the sole control and
  help remains hidden by default. Challenges previously violated this rule and
  its XP/help text was moved into the toggle.
- Weapon catalog effect ID `0x45EA9E3E` is proven by decompiled `shop_handheld`
  to feed `WeaponAccuracyDiff`; `0x77323E93` feeds Power and `0x9D36F302` Range.
  These values drive displayed shop stat comparisons. They are not the same as
  weaponcomponents.meta mechanics. Wide Cattleman sight: CameraFovModifier .95,
  AccuracyModifier 1.0, so FOV does NOT itself change bullet accuracy. Effects
  UI carries a hover explanation on these IDs.
- Editor server must NEVER launch a browser or call `webbrowser.open`; Lexer
  reports every automatic launch steals focus. `server.py` now serves only and
  prints the URL. Browser opening is exclusively a user action.
- TODO #36 (WAITING): every Bandit challenge rank unlocks new fence inventory;
  needs a ten-rank reward map. TODO #37 (WAITING): inventory and redesign all
  trinket/talisman effects. Lexer explicitly directed FEATURES entry 2 with `*`
  as a planned exception: self-sufficient crafting without fence/trapper travel;
  it is visibly marked not implemented/confirmed.
- The two vanilla `Buzzed` hairstyle catalog records (`0x44EAB19E` at $0.50,
  `0xACFEB669` at $5.00) are genuine duplicates in the same barber inventory
  and catalog page with the same localization and artwork. Their only observed
  record differences are price and multiplicity slot (`WARDROBE_HAIR` versus
  `ANY`); do not invent a more specific user-facing distinction without new
  evidence.
- Header dataset picker is one compact overlaid control: visible dataset name,
  tiny path in the remaining middle space, and dropdown chevron at the far
  right. The chevron is CSS-drawn, never a literal `v`/text glyph. Sort
  convention is deliberately down-arrow = ascending/A-Z.
- Catalog multiplicity rows can be created, not merely edited. The Items carry
  column offers `+ carry rule` for known base/satchel/upgrade slots; saving a
  new rule creates the corresponding `<multiplicity><item>` record.
- TODO #34 is intentionally WAITING while Lexer designs it: challenges replace
  native health/stamina/Dead Eye XP progression, three strands grant attribute
  ranks, other ranks unlock thematic recipes, challenge UI previews rewards,
  and occasional empty-meter tutorials explain the new progression system.
- Attribute XP source finding: `stats_sp.meta` declares RPG rank/points storage
  but does not list gameplay award sources. Ordinary health/stamina/Dead Eye XP
  is issued throughout compiled scripts through `SET_ATTRIBUTE_POINTS` /
  related native logic, so there is no single data file to zero. Challenge XP
  is data-driven in `challenges_sp.meta`: FIRST/SECOND/THIRD/FOURTH reward
  enums mean 25/50/100/150 XP for each attribute. Cumulative ordinary ranks are
  0, 50, 100, 200, 350, 550, 800, 1100 XP (levels 1–8); 9–10 are bonus ranks.
  A challenge-only progression overhaul therefore needs GameplayTweaks to
  clamp/reject external point gains or set ranks deterministically, even though
  challenge reward selection itself is editable data.
- TODO #35 is WAITING design work: challenge bandoliers, gun belts, and other
  reinforced equipment must not duplicate ordinary purchasable gear. Their
  benefits must remain meaningful across the many ranks that use equipment as
  rewards, without forcing the player to wear an unwanted visual outfit.
- Effects UI: Used By opens the specific localized catalog items and links each
  back to Items. The record schema always stores Value and Percent, but behavior
  branches need not consume both. Decompiled `eating_scenario.c` proves core
  restoration returns nonzero Percent directly, else falls back to
  `Value / 8 * 100`; direct bar branches consume Value. Decompiled shop UI code
  proves weapon-stat IDs 0x77323E93/0x45EA9E3E/0x9D36F302 consume Value
  (`vVar22.z`) for stat comparisons, not Percent. Do NOT universally synchronize
  the two. LEXEDITOR makes known-unused fields read-only and labels the active
  role; unknown Behavior IDs retain both pending identification.
- Decompiled `eating_scenario.c` calls `_ITEM_DATABASE_FILLOUT_ITEM_EFFECTS_IDS`
  and loops over every returned effect (array capacity 20); multiple core
  effects on one provision are supported and are not first-effect-only. Its
  core branches use Percent when nonzero, otherwise Value/8. Therefore missing
  secondary provision effects indicate stale/invalid runtime data or script
  interference, not an inherent one-effect catalog limit.
- LEXEDITOR must not confuse catalog purchase yield with shop inventory
  requirement-group `count`. For example, `AMMO_ARROW` has acquire-cost
  quantity 5 (five arrows per $0.50 purchase), while its shop entries contain
  counts such as 1, 20, 50, and -1. Those counts are shop-specific listing/
  availability metadata, not bundle size. The Items and Shops Purchase Output
  controls edit catalog purchase yield; known container products additionally
  display their effective loot-table contents without conflating the fields.
- TODO #51 covers permanently loseable unique weapons: after acquisition, a
  unique thrown/dropped weapon that no longer exists in inventory, horse,
  locker, or as a live world pickup should become recoverable from the weapon
  locker. The implementation must inventory all affected uniques and prevent
  duplication across projectile, pickup, unload, mission, save, and reload
  states.
- Collectible icon alternatives must come from an atlas that Story Mode can
  actually resolve. Cards have a strong existing candidate in `BLIP_MG_POKER`.
  Dreamcatchers have no exact SP icon: `BLIP_MP_COLLECTOR_MAP` is thematic but
  requires an in-game SP-loading test; `BLIP_AMBIENT_SECRET` and `BLIP_POI` are
  generic fallbacks. `BLIP_OVERLAY_RING` is an overlay asset and looks like a
  hollow circle when misused as the primary sprite. A faithful dreamcatcher
  symbol requires a working custom texture-dictionary pipeline.
- Custom collectible icons appear technically solvable, but are not just PNG
  generation: build an RDR2-compatible texture dictionary (investigate
  Sollumz_RDR/compatible YTD tooling), load or patch the blip atlas through
  LML, pass its texture hash to the blip native, and test Story Mode lookup.
  OpenIV 4.1 still cannot author the required RDR2 texture dictionary.
- Texture-tool audit 2026-07-13: RDR2 Texture Toolkit can build an RDR2 YTD
  from DDS inputs but delegates final conversion to a binary supplied by a RedM
  installation; RedM is not installed. The current Sollumz_RDR branch supports
  embedded texture dictionaries in drawable XML but has no standalone YTD
  importer/exporter. Icon masters/spec live under GameplayTweaks/icons; final
  packaging still needs either RedM's converter or a new standalone serializer.
- TODO #55 Breakdown is built/installed and awaiting in-game confirmation.
  Rockstar's `simple_crafting` hard-codes six filters (`filterCount=6`, indices
  0..5), so XML cannot add a seventh category. GameplayTweaks now extends the
  live `CraftingDatastore` to seven, labels index 6 `LEX_CRAFT_BREAKDOWN`, and
  injects a normal recipe row whose output/cost are handled by the existing
  crafting transaction. MyOverhaul adds `LEX_GUNPOWDER`, cap 20, with five
  alternate COST_CRAFTING inputs: 10 regular revolver/pistol/repeater/rifle
  rounds or 5 regular shotgun shells yield 1. Treat this as experimental until
  filter navigation, variant selection, inventory consumption/output, and
  crash safety are confirmed in game.
- TODO #52 Hunter's Hatchet description is now saved: instantly kill any
  animal without reducing carcass quality. It is ACTIONABLE. TODO #53
  separately removes the fixed Hunter's Hatchet and Rusted Hunter's Hatchet
  world placements. TODO #54 is the roster-wide unique-weapon usefulness pass.
- Collectible map categories and current primary sprites (2026-07-13): card =
  BLIP_AMBIENT_NEWSPAPER, bone = BLIP_ANIMAL_DEAD, carving =
  BLIP_AMBIENT_SECRET, dreamcatcher = BLIP_OVERLAY_RING, grave =
  BLIP_AMBIENT_DEATH, exotic = BLIP_PLANT, legendary fish = BLIP_MG_FISHING,
  shack = BLIP_PROC_HOME, treasure clue/map = BLIP_CHEST, POI = BLIP_POI.
  The first six except exotic are misleading/placeholders and form the custom
  icon set: cigarette card, dinosaur fossil, rock carving, dreamcatcher,
  grave/headstone, and treasure map. The recognizable vanilla house, plant,
  tent, paw, fish, and pin glyph concepts are retained, but every proposed
  marker uses a black circular medallion; bare plant/paw/fish sprites are not
  visually acceptable. The proposed complete legend
  also includes Legendary Animals (`BLIP_ANIMAL`) and fixed Story Mode Gang
  Hideouts (`BLIP_REGION_CARAVAN`), for twelve categories total. Legendary
  animals must be represented as territory/search-zone points because the
  tracked animal spawns after its clue sequence; legendary fish use a
  representative point within their fishing area. Shacks and hideouts are
  fixed points. Use **Shacks** as the category label even though individual
  discoveries may properly be named Cabin, House, Homestead, etc. The visual review sheet is
  `GameplayTweaks/icons/map-icon-proposals.html` and must judge every symbol at
  actual 24 px size, not only as enlarged artwork. The approved workflow is
  raster generation, not hand-authored SVG. Six custom symbols now have
  AI-generated high-resolution raster masters reduced to 32/24 px. Shacks and
  Gang Hideouts use exact extracted vanilla sprites; Exotics, Legendary
  Animals, and Legendary Fish use exact extracted glyph pixels composited on
  black medallions; POI is unchanged. Never label a traced approximation
  "vanilla glyph."
- Items plant/herb classification (2026-07-13): Rockstar's literal
  `CI_CATEGORY_HERBS` contains only 7 catalog records. The full collectible
  plant set is split across HERBS (7), INGREDIENT (17), PROVISION (9), and
  VALUABLE (13). LEXEDITOR's synthetic PLANTS / HERBS view must derive its 46
  records from `CONSUMABLE_HERB_*` plus direct `loot_table_herb.meta` sources,
  compute the count dynamically, and clear an incompatible group filter when
  selected. The UI label is simply `PLANTS`, alphabetized like every other
  category; never expose the synthetic implementation or count in the label.
- LEXEDITOR item-effect assignment commits only on Enter after resolving an
  exact known effect. Blur, browser-tab switching, and partial datalist text
  must never mutate an item's effects. Item price/listing warnings are compact
  right-aligned `!` badges inside the numeric control, with detail on hover.
- Custom item creation is supported through Items `+ NEW ITEM` and
  `/api/catalog/create`. It clones only the proven minimal `LEX_GUNPOWDER`
  material shape, strips inherited costs/effects, creates independent name and
  description localization keys, and leaves all normal item editing available.
  The editor must remain usable against any writable mod root; this is not a
  MyOverhaul-only hardcoded item operation.
- Horse bonding is attribute `PA_BONDING` index 7. It is ranks 0-4 with
  model/data-defined point thresholds, not a universal 0-100 meter.
  GameplayTweaks `[HorseBonding] SugarCubeBonusPoints` adds configurable points
  when `CONSUMABLE_SUGARCUBE` decreases near the current/recent owned horse;
  the default is 10 and requires in-game confirmation for mounted/on-foot feeds.
- LEXEDITOR consistency update (2026-07-13): Challenges and Weapons use the
  same full-width `subtabs` component as Loot Tables. Main-record localization
  inputs must use the dark shared control styling; never allow browser-default
  white fields with yellow text. Weapon scalar editing is schema-aware:
  numeric fields use numeric inputs, finite vanilla-proven identifier domains
  use selectors (including AccuracyInfo and AIAttackModes), and only genuinely
  open, high-cardinality identifier/hash fields remain free text. Direct
  `#tab` URLs restore that tab on load for headless QA and normal deep links.
- Food-bait finding/rework (2026-07-13): vanilla Bread, Cheese, and Corn Bait
  are not ordinary stacks; each is an `UPGRADE_FSH_BAIT_*` permanent
  entitlement with `SLOTID_ANY=-1` and the otherwise-exclusive tag
  `0x7B0756FF`. Consumed worms/crickets use the same category/flags but ordinary
  `CI_TAG_CATEGORY_KIT` + `CI_TAG_ITEM_KIT` tags and finite multiplicity.
  MyOverhaul now converts the three food baits to that live-bait shape: base
  satchel capacity 5, matching cumulative upgrade contributions, and an
  always-known portable recipes. Lexer subsequently set the saved outputs to
  5 Bread Bait per Bread Roll, 5 Cheese Bait per Cheese Wedge, and 3 Corn Bait
  per Corn. This is structurally/data-feasible but must be confirmed in-game:
  verify one unit disappears after successful bait use, zero count removes it
  from selection, and an existing save's old permanent entitlement does not
  cause automatic replenishment. LEXEDITOR labels the vanilla `-1` food-bait
  rule as `permanent / unlimited`; never present it as an ordinary carry cap.
- Item-to-Shops navigation must never select an arbitrary merchant. Buy links
  open an All Shops view with one row per actual catalog shop listing. Sell
  links open the item's generic resale record without implying a buyer.
  Actual merchant acceptance is separate `PDATA_SHOP_INVENTORIES` data queried
  as `shopInventories/shopSellableItems(shopType=%x)`; load that buyer map
  before showing a buyer list. The local RPF8 extractor can now inspect CRC-
  mounted archive headers from `pfm.dat`; its code/binaries stay gitignored.
  Until that buyer map is loaded, every defined sell payout must be labeled
  `Payout set; buyer list is separate`; never falsely warn that no shop buys it
  or imply that `shopsinventories` governs player-to-shop sales. Sell links
  must exact-match the requested catalog ID and expose no purchase-stock action.
- Worms and crickets use paired records intentionally. `_WORM_CAN` and
  `_CRICKET_TIN` are purchased container products; the acquisition script maps
  them to `BAIT_WORMS` / `BAIT_CRICKETS` in `loot_table_itemgroups.meta`, each
  of which grants five plain `_WORM` / `_CRICKET` fishing consumables. The raw
  catalog acquire quantity therefore does not by itself describe usable bait
  received. LEXEDITOR shows both layers under Purchase Output and links bundle
  contents to the editable loot table; never call these records duplicates.
- TODO #56 is the requested in-game test pass for every bait modified in the
  Items `UPGRADE` category: purchase and craft each one, then verify price,
  effective output, ingredients, recipe yield/station, carry cap, and actual
  finite consumption for Bread, Cheese, Corn, Worm, and Cricket bait.
- LEXEDITOR pending edits are cross-tab state, not tab-local previews. Items
  and Shops must both immediately reflect unsaved buy/sell prices, purchase
  output, and shop memberships. The Items `Priced, but not listed` warning must
  query the loaded mutable shop inventory rather than stale catalog
  `shopListings`; switching tabs must never require Save merely to see the same
  pending values.
- LEXEDITOR repair pass (2026-07-13): shared Rockstar localization keys must
  fork to an item-specific key on first edit so changing one item never silently
  renames/redescribes another. Container bundle output quantities edit the
  owning item-group loot entry directly. Carry-cap pickers display the same
  recovered labels used by rows and always include both ammo upgrades and the
  Legend of the East slot; the per-item LotE toggle targets a combined cap of
  999. All subtab bars use the shared `subtabs` component, including AI.
- Breakdown membership is explicit editor data in
  `GameplayTweaks/breakdown_recipes.csv`, not a hidden hardcoded Gunpowder case.
  The Crafting tab's Menu category selector assigns an output to the script-
  added Breakdown filter; GameplayTweaks loads every listed output and its
  current number of alternate catalog recipes.
- Cigarette-card batch convention (2026-07-13): all 144 individual cards use
  `<Set> Card №<n>` names and `Card #<n> of 12.` description prefixes, matching
  Lexer's Amazing Inventions edits. All remain unsellable until TODO #57 adds
  per-set post-turn-in duplicate resale.
- Self-sufficient vendor crafting (2026-07-13): all 140 catalog recipes that
  used `COST_CRAFTING_TRAPPER` or `COST_CRAFTING_FENCE` now use portable
  `COST_CRAFTING`. The 121 `CURRENCY_CASH` service-fee ingredients were
  removed; none of these records used cash as a physical recipe component and
  no affected output already had a conflicting portable variant. The editor
  server applies the same normalization to future recipe saves so stale tabs
  cannot restore vendor-only contexts. This remains unconfirmed in game, so
  the existing starred FEATURES entry stays starred.
- LEXEDITOR save-state rule: every tab rerender that constructs a savebar must
  refresh the single global header SAVE state. This specifically fixes Crafting
  picker/add/remove actions that previously showed an unsaved count while the
  disk icon remained disabled until another tab was opened. Headless interaction
  QA confirmed an add-ingredient action immediately enables SAVE.
- Crime & Law uses the shared full-width subtab component: `Crime Rules` owns
  `crimeinformation.meta`; `Dispatch & Wanted` owns `dispatch.meta`. Dispatch
  must never be appended as a second long table beneath all crime rows.
- Vanilla simple crafting has six hard-coded output predicates, not a recipe
  category field: Provisions = food consumables plus coffee; Tonics =
  `CI_TAG_ITEM_MEDICINE`/`REMEDY` excluding horse items; Ammunition = AMMO
  excluding thrown; Weapons = WEAPON or thrown ammo; Hunting =
  `CI_TAG_ITEM_HUNTING`; Horse Care = `CI_TAG_ITEM_HORSE_ITEM`.
  `COST_CRAFTING_*` selects station/alternate formula only. LEXEDITOR derives
  and names the vanilla category from group/tags. Its optional Breakdown
  selector is discovered from `GameplayTweaks/breakdown_recipes.csv`; without
  that extension, ordinary catalog/crafting editing remains fully usable.
  `LEXEDITOR_MOD_ROOT` and `LEXEDITOR_MOD_NAME` point the editable dataset at
  any user's own LML mod directory; `LEXEDITOR_BREAKDOWN_FILE` optionally
  locates that user's script-backed category sidecar. MyOverhaul is only the
  default local profile, not an editor runtime requirement.
- Custom collectible icons are built reproducibly by
  `GameplayTweaks/icons/build_ytd.ps1`: project PNG -> DXT5 DDS -> WesternGamer's
  MIT RDR2 Texture Toolkit -> official RedM CitiCon RSC8 conversion. The output
  `lex_map_icons.ytd` contains nine `lex_blip_*` textures and is installed as
  `lml/stream/LEX_MAP_ICONS.ytd`. GameplayTweaks now uses those hashes for
  cards, bones, carvings, dreamcatchers, graves, exotics, legendary fish, and
  treasure clues; shacks/POIs retain vanilla hashes. The ASI explicitly
  requests `lex_map_icons`, waits for the streamed dictionary before creating
  collectible blips, and records existence/load state in
  `GameplayTweaks.map-icons.log`; the earlier build omitted this required
  runtime request. Rendering awaits a full-restart game test. The
  legendary-animal texture is packaged but no
  legendary-animal locations exist in the current collectible CSV.
- 2026-07-16: the Story loader stack was restored from
  `_online_mode_disabled` while the currently running clean launch remained
  open; it becomes active only after a full RDR2 restart. To eliminate stale
  editor/install copies, `<game>\lml\MyOverhaul` is now a directory junction
  to `C:\RDR2Mod\MyOverhaul`. Every completed LEXEDITOR save therefore writes
  the exact files LML loads on the next game launch. The displaced installed
  copy is retained at
  `C:\RDR2Mod\_installed_MyOverhaul_backup_20260716-005030`.

