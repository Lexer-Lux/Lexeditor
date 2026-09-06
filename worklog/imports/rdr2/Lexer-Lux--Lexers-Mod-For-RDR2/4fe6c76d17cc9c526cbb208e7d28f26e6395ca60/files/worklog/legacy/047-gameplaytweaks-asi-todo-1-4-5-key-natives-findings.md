# Worklog: 047 Gameplaytweaks Asi Todo 1 4 5 Key Natives Findings

## GameplayTweaks.asi (TODO #1/#4/#5) — key natives & findings

- Cores read via `_GET_ATTRIBUTE_CORE_VALUE(ped,0|1|2)` → 0..100. Bar regen:
  `SET_PLAYER_HEALTH_RECHARGE_MULTIPLIER`=0x8899C244EBCF70DE,
  `SET_PLAYER_STAMINA_RECHARGE_MULTIPLIER`=0xFECA17CF3343694B. Deadeye trickle:
  `_SPECIAL_ABILITY_RESTORE_BY_AMOUNT`=0x51345AE20F22C261 (amt,0,0,1). Minimap:
  `SET_RADAR_ZOOM(int)`=0xCAF6489DA2C8DD9E (scale undocumented → ini-tunable).
  Attribute/core enum lives on `SET_ATTRIBUTE_BASE_RANK` (PA_HEALTH… SA_HUNGER,
  SA_BODYWEIGHT… — the "cores" are the 3 ATTRIBUTE_CORE_*; the softcore stats
  like SA_HUNGER/SA_BODYWEIGHT are separate attributes).
- **#3 dead ends worth remembering:** no native sets core-DRAIN rate (only
  stamina/eagle-eye/deadeye *depletion* multipliers exist, not the 3 cores),
  and no metabolism/core-drain tuning file is in the extracted RPFs. Weight/
  mounted core-drain modifiers appear engine-hardcoded → not data-removable.
- **#1 limitation and enforcement build:** no data field/native directly turns
  off reserve behavior. On 2026-07-14 GameplayTweaks added an enforcement
  approximation: zero outer Health kills, zero Stamina blocks sprint and sets
  exertion depletion to zero, and zero Dead Eye disables Dead Eye until the
  ring refills. The cached Dead Eye amount failed to catch the boundary in the
  first test; the 2026-07-15 build also detects a falling Dead Eye core while
  the ability is active, restores that first reserve tick, and disables the
  ability. It is gated off during fades/control locks and is awaiting
  tests that the three engine fallback paths respect those controls without
  disturbing passive core metabolism, items, sleep, missions, or respawning.
- **#5 limitation:** kill/headshot deadeye refill not found in data or natives;
  GameplayTweaks adds core-based regen on top rather than replacing kill-gain.
- 2026-07-14: TODO #21 is now a shared in-game-time CoreClock in
  GameplayTweaks. Awake clock minutes drain Health, Stamina, and Dead Eye cores
  independently; each defaults to 100-to-0 in 24 in-game hours. Detected sleep
  continues Health/Stamina drain but refills Dead Eye; 12 sleep hours defaults
  to 0-to-100, so 16 awake hours followed by 8 asleep restores Dead Eye from
  roughly one-third to full. `[CoreClock]` exposes Enabled, the three
  `*DrainHours`, and `DeadEyeSleepRefillHours`. Fractional points accumulate so
  rates remain exact despite integer core natives. CoreClock keeps an
  authoritative managed value: positive live changes and substantial negative
  item/script effects are accepted, while single-point lower live values from
  Rockstar's background metabolism are restored. It does not write unchanged
  core values every frame, because that can race consumable-effect processing.
  The configured drain therefore does not stack with vanilla. Sleep detection
  is still a fade/control-lock
  heuristic and must be tested against fast travel and mission time skips.
- 2026-07-14 provision-effect fault investigation: the installed catalog hash
  matched MyOverhaul, LML confirmed it was active, and a runtime probe confirmed
  the affected items' effect-reference arrays loaded. The shared effect table
  nevertheless contained four invalid decimal `value` fields (`2.5`/`7.5`) in
  custom horse effects; Rockstar's runtime effect-info structure stores Value
  as an integer. They were repaired to `3`/`8`, and LEXEDITOR now constrains
  Value, Time, and Time Units to integers while Percent remains decimal. The
  temporary probe remains in the current test ASI and must be removed after
  confirmation. Do not treat the repair as proven before the restart test.
- The follow-up v3 probe showed selective definition lookup failures. The first
  readable-vs-hash theory was disproved: OpenIV's raw vanilla table confirms
  every readable key is exactly its JOAAT hash. The decisive structural
  difference is ordering: vanilla and Kiddo definitions are strictly ascending
  by numeric key, while MyOverhaul had 16 inversions introduced around custom
  effects. MyOverhaul now stores explicit numeric keys and all 373 definitions
  are sorted with zero inversions. LEXEDITOR canonicalizes keys and re-sorts the
  complete definition table on every catalog save, so future custom effects
  cannot recreate this fault. This awaits one restart/runtime-probe confirmation.
- 2026-07-12: TODO #26 plant density is built in GameplayTweaks using
  GET_SCENARIO_POINTS_IN_AREA, _GET_SCENARIO_POINT_TYPE/COORDS, and
  _SET_SCENARIO_POINT_ACTIVE. All 50 world-brain plant scenario types from
  wb_herbs.meta are deterministically thinned by location; default is 0.5.
- CORRECTION 2026-07-12: Lexer rejected scenario-point deactivation because it
  may leave plants physically visible but unusable. Its runtime code and INI
  section were removed entirely. Do not restore it without a true spawn/
  placement-density solution.
- Lexer combined BLOCKED and WAITING conceptually; follow the current TODO.txt
  section structure rather than recreating a distinction he does not want.
- Do not commit or push unless Lexer explicitly asks.
- CREDITS.txt is public-facing and organized by relationship: Required,
  Included, Research & Reference (grouped by subject), Tools & Resources,
  Compatibility, and Supersedes. Categories replace per-entry reason essays;
  never expose internal TODO numbers there. Do not credit merely planned or
  unused references. Add a mod to Supersedes only after its complete relevant
  functionality has been implemented and confirmed in game.
- Effects identity in LEXEDITOR: there are two game identifiers, not three
  names. The catalog reference is stored by item effect lists and is commonly
  only a JOAAT `0x...` hash; the Behavior ID independently selects the engine
  operation. Human labels in `editor/labels.json` are editor-only. A recovered
  `EFFECT_*` key is shown only for an exact JOAAT match. Never call hashes
  opcodes or treat an unresolved symbolic key as a missing/invalid effect.
- RDO safety: this heavily modded game root cannot be treated as an Online-safe
  install merely because MyOverhaul edits SP files. `Enable Online Mode.bat`
  uses `Switch-RDR2Mode.ps1` to move every ASI plus dinput8/ScriptHook and
  VFS/LML out of the launch path; `Restore Story Mode Mods.bat` restores them.
  The 17-item round trip is tested. Never launch RDO with the Story mod loader
  stack active. CORRECTION 2026-07-15: moving that stack also disables every
  Story Mode mod and is not an acceptable automatic "fix" for Online. Never
  switch modes or relocate the stack without Lexer's explicit confirmation.
  A mistaken switch is currently awaiting restoration because RDR2 is running;
  restore it as soon as the game is closed, without launching the game.
- Premium-cigarette card rewards cannot be expressed by catalog effects or
  loot tables: effects invoke fixed Behavior IDs, while loot tables roll on
  loot/container interactions rather than consumable use. TODO #66 therefore
  requires script-side detection of actual Premium Cigarette consumption, a
  20% RNG roll, and a random card inventory grant; buying/opening/discarding
  must not trigger it.
- TODO #66 is built and staged as of 2026-07-16. GameplayTweaks snapshots all
  144 card counts after startup and suppresses only the next card increase
  paired with acquiring a Premium Cigarette pack. Loose world-card pickups
  remain collectible and preexisting cards remain owned. It recognizes smoking through the active
  item-interaction's `CONSUMABLE_CIGARETTE_BOX` ID plus an actual count drop,
  so buying, looting, or discarding cannot roll. Each use rolls 20%; unowned
  cards are selected first, then duplicates after completion. This requires
  in-game confirmation of the interaction ID, notification, and mission/set
  progression before completion.
- RDO-style fast human-corpse looting is data/animation feasible. Existing
  references identify `lootconfigdata.meta` animation-rate selectors, and the
  SP/MP animation sets can be compared for the short RDO interaction. TODO #67
  is intentionally narrow: do not globally accelerate skinning, gathering,
  crafting, carrying, prompts, or unrelated interactions.
- Cores-as-backup-bars has no direct engine toggle. Do not claim it is natively
  disabled; TODO #1's installed build enforces equivalent player-facing rules
  through outer-bar checks and must be confirmed in game.
- 2026-07-15 reserve-core retest proved the first enforcement build was too
  narrow: it did not interrupt an already-running sprint, cover bow/lasso/
  melee, or handle mounts. The replacement guards those action controls at the
  ring boundary and restores any player/horse stamina-core reserve tick that
  slips through. It still requires tests of sprint, bow, wrangling, melee,
  horse sprint, and horse jump before reserve behavior can be called solved.
- A second 2026-07-15 test proved that control suppression plus depletion=0
  still does not cancel Rockstar's already-running locomotion task. The next
  build therefore caps the ped/mount move-blend task itself at an empty outer
  ring, restores any slipped core tick, and unconditionally disables Dead Eye
  plus all four special-ability controls at its empty-ring boundary. This is
  staged in the disabled Story stack and remains unconfirmed; do not imply that
  every non-locomotion stamina consumer has a universal engine gate, because no
  such native has been identified.
- 2026-07-16 GameplayTweaks test batch: TODO #33 clears invincibility/proofs on
  nearby `_IS_PED_CHILD` peds only while no mission is active; #44 doubles only
  small positive honor changes immediately following `INPUT_INTERACT_POS` while
  the Viking Comb is carried; #46 tags player-caused Viking Hatchet corpses and
  adds four times only the cash observed during that corpse's completed loot
  interaction. All three remain TESTING until confirmed in game.
- TODO #50 is implemented as an ASI-owned persistent bloodstain. Free-roam
  death removes the unprotected share of current cash, replaces the prior
  stain, resolves its position through `GET_SAFE_COORD_FOR_PED` with a ground-Z
  fallback, creates a death blip/world marker, and restores the cash on touch.
  `GameplayTweaks.bloodstain.dat` persists the state. The first active Gambler
  goal determines completed rank count; each rank protects 10%, rank 10 all.
- TODO #13's runtime pickup-light suppression and generated 80-model weapon map
  are built, but this is not the complete requested feature yet: catalog hat
  records contain no model identifier, so owned collectible hats still require
  a proven metaped-item-to-world-pickup-model join. Never call #13 complete on
  the weapon-only build.
- Catalog cash sellability is controlled by a COST_TYPE_PRICE/CURRENCY_CASH
  record under `<sellprices>`. LEXEDITOR now adds/removes that record. All 144
  `DOCUMENT_CIG_CARD_<set>_<number>` records are unsellable in MyOverhaul.
- A catalog `<sellprices>` / `SELL_SHOP_DEFAULT` record defines payout but does
  not choose the buyer. `shopsinventories` controls what merchants sell TO the
  player, not what they buy FROM the player. Vendor buy-interest is filtered by
  `PDATA_SHOP_INVENTORIES`, queried by the shared shop script before a sale.
  As of 2026-07-15 LEXEDITOR edits that buyer map independently: GameplayTweaks
  performs a one-shot runtime vanilla dump, the editor preserves unresolved
  hashes, and its You Sell merchant toggles write a complete
  `parseddata/0x0BA63B3D.ymt`. Never describe purchase-stock assignment as buyer
  assignment or put purchase-stock actions in You Sell.
- Player-to-merchant acceptance is stored in parsed data
  `0x0BA63B3D.ymt`: `SHOPTYPE` attributes own lists of `ITEMID` attributes via
  `SHOPINVENTORIES/SHOPSELLABLEITEMS/INVITEM` data nodes. The separate
  `0x9CEB6AD5.ymt` is joaat(`shop_inventories`) and contains physical/general
  shop definitions; it is not the primary sellable-item list. This schema was
  learned from All Items Unlocked 1.3.5, but its all-items list is never copied
  or used as the baseline. The baseline is now dumped at runtime from the
  user's loaded vanilla PDATA before buyer editing is enabled.
- Collectible-map scope includes cards, bones, dreamcatchers, rock carvings,
  graves, POIs, exotics, legendary fish, shacks, and treasure-map clues/pickups, but excludes actual
  treasure caches so treasure maps retain their purpose.
- The #19/#20/#28 reference archives were supplied. #19 wagon-core drain
  and #20 replacement train tracking are built/installed in GameplayTweaks and
  await testing. Downloaded Train Tracker 1.1 was byte-identical to the
  installed ASI; the old file is renamed TrainTracker.asi.disabled.
- #28 collectible map is built/installed in GameplayTweaks with a separate
  `collectibles.csv`: 581 named locations across cards, bones, carvings,
  dreamcatchers, graves, exotics, legendary fish, shacks, Points of Interest,
  and treasure clues.
  Eight actual treasure caches are excluded. Coordinates are transformed from
  Shackmaps/MapGenie public map projections by our reproducible
  `_downloads/build_collectible_locations.py`; category toggles live in
  `[CollectibleMap]`. It needs in-game projection, icon, legend, and blip-count
  testing. Cards/bones/carvings/fish gate on their vanilla introduction
  documents; exotics gate on the five `DOCUMENT_NOTE_EXOTICS_STAGE_*` request
  lists. Shacks are immediately visible. Completion-state hiding is not built.
- Thrown catalog entries (`WEAPON_THROWN_DYNAMITE`, etc.) have multiplicity 1
  because they represent the owned weapon instance. Usable capacity belongs to
  the corresponding `AMMO_*` catalog entry (vanilla dynamite is 8). LEXEDITOR
  identifies this and links directly to the capacity-bearing ammo record.
- `weapons.ymt` ammunition is layered. `CAmmoInfo` stores shared behavior
  (bleed-out, skin penetration, impact count, Dead Eye drain, reward/stat IDs),
  while each `CWeaponInfo/DamageInfos` has an ammo-keyed variant containing the
  actual per-weapon Damage, Penetration, optional AccuracyInfo, and optional
  DamageFallOffInfo. High Velocity range is represented by referenced falloff
  curves with distance/damage points. LEXEDITOR's Ammo Types view now joins and
  edits both layers; do not present the standalone CAmmoInfo row as the complete
  ammo performance definition. Radial stat bars are summaries, not a separate
  authoritative editable stat table.
- Effect labels in `editor/labels.json` may use recovered symbolic `EFFECT_*`
  keys while normalized catalogs store the same key as its `0x%08X` JOAAT.
  `get_labels()` must expose both aliases dynamically; label saving writes only
  the exact edited key to the raw file. Do not canonicalize catalog keys without
  preserving this join, or labels such as Dead Eye Core -6.25% disappear.
- Catalog prices do not prove an item is purchasable: shop membership lives in
  `shopsinventories`. Vanilla standard shops list `AMMO_DYNAMITE`, not
  `WEAPON_THROWN_DYNAMITE`; the ammo offer's acquire-cost quantity controls how
  many units a purchase grants. Shop requirement-group counts are separate
  availability/listing metadata. LEXEDITOR labels priced-but-unlisted records
  as not sold in standard shops.
- LEXEDITOR UI baseline (2026-07-12): filter rerenders must preserve typing
  focus; page-width tables must not force a document scrollbar; every tab uses
  the single toolbar `?` to toggle at most one help panel. Crafting uses the
  shared table layout with localized output/ingredient names and a separately
  labeled station/context column. Loot file selectors are full-width tabs and
  referenced table entries display inline without a disclosure button.
- Items effect autocomplete must never rerender the Items table during ordinary
  typing. A known effect commits only through an explicit datalist selection,
  change, or Enter, and chip add/remove updates its cell locally so focus and
  scroll position remain stable.
- A tab renderer called directly by its own filters/subtabs must reinstall the
  shared file-context/help control before returning. Help panels must be
  conditional on `state.helpOpen[tab]`; never append one unconditionally and
  rely on the outer `render()` wrapper to hide it.
- Do not claim or open Lexer's visible editor tab for routine testing: doing so
  can foreground the browser and steal focus. Prefer API calls, static JS
  syntax checks, and server tests; use browser control only when visual or
  interaction verification is genuinely necessary and keep it background-only.
- Carry-cap semantics: `SLOTID_ANY` is the fallback/default inventory context.
  `0` contributes no capacity there (specific Satchel/upgrade slots may supply
  the real limit); `-1` means no numeric catalog cap in that context, not proof
  of unlimited practical carrying. `0x550898DE` and `0xAEEE1782` remain
  unresolved engine slot hashes. Both are usually -1, but names were not found
  in the unhashed corpus and camp/horse/context meanings are unproven; never
  label them as known infinite contexts.
- Item Sources in LEXEDITOR indexes standard shop listings/quantities, crafting
  outputs, direct loot-table item entries with rate/condition, and skinning
  yields. It explicitly does not yet cover fixed world placements, scripted
  mission rewards, or other dynamic grants.
- TODO #68 expands Item Sources into complete acquisition provenance. Keep
  confirmed acquisitions (shops, crafting, loot, skinning, fixed placements,
  scripts/missions, rewards, and dynamic grants) separate from mere script
  references. "No known source / possible cut content" is valid only after all
  indexed layers are searched; missing shop/loot membership alone is not proof.
- `loot_table_herb.meta` contains 44 plant loot tables / 58 entries: ordinary
  herbs, four berries, four mushrooms, three spices, and thirteen orchids.
  LEXEDITOR must clear the shared loot search when switching loot subtabs so a
  query from Peds/Containers cannot make the Herbs tab appear incomplete.
- TODO #32 Female Fertility Statue: unique carried buff is Mother's Bounty
  (every harvested plant grants one matching extra item, 100% chance), plus
  unsellable status and optional collectible map marker. Implement the bonus
  script-side after detecting a successful gathering event. Armed-child-Jack
  is only an experimental optional idea: verify child ped weapon/combat/anim
  support and isolate it from missions before treating it as feasible.
- TODO #33 removes child NPC invincibility. Determine whether protection comes
  from ped health profiles, damage proofs/flags, relationship/mission state, or
  repeated runtime invincibility calls; avoid blindly stripping protection
  from story-critical mission actors before compatibility is understood.
- TODO #22 no-auto-ammo is built from the effective lootconfigdata schema by
  removing every TAKE_AMMO QuickBehavior. It is mapped in MyOverhaul/install.xml
  and installed separately as `lml/LexNoAutoAmmo` for isolated testing without
  activating the rest of MyOverhaul.
- TODO #27 overflow storage is not feasible with the known API: rejected
  acquisitions at a carry cap emit no identified universal event/hook, so
  polling cannot capture what never entered inventory. Infinite Inventory's
  highest-count restoration is not an overflow mechanism. Keep #27 dropped
  unless a genuine rejected-acquisition interception point is found.

