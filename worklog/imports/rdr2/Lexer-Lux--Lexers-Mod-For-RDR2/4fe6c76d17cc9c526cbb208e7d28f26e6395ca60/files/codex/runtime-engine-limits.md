# Confirmed runtime behaviour and engine limits

- The weapon-out DIVE is `mech_weapons_core@base@dive@{pistol,rifle,unarmed}@`
  `{launch,prone,getup}` — a three-part sequence, not a roll. A combat ROLL also
  exists in the engine: `anim/move_networks/move_networks.xml` carries
  `TaskCombatRoll` as `SP_SINGLEPLAYER_RESIDENT`, `action/special_conditions.meta`
  tests `IsDoingCombatRoll`, and `PED::GET_PED_IS_DOING_COMBAT_ROLL`
  (`0xC48A9EB0D499B3E5`) reads it. Nothing STARTS one from script: the only entry
  point is `DEPRECATED_SCRIPT_TASK_COMBAT_ROLL` and no shipped script calls it.
  The clips ship as archive entries (`COMBATROLL_FWD_P1_{00,45,90,135}`,
  `COMBATROLL_BWD_P1_{135,180}` and the matching `P2` set). The shipped
  animation index and runtime resolver confirm their dictionary is
  `mech_strafe@generic@roll@base`. These clips carry authored root motion; stop
  incoming horizontal momentum once and let the animation move the ped rather
  than driving velocity throughout the roll.
- `STREAMING::DOES_ANIM_DICT_EXIST` (`0x537F44CB0D7F150D`, in the SDK header)
  validates an animation dictionary name WITHOUT streaming it, and
  `ENTITY::GET_ANIM_DURATION` returns 0 for a clip a loaded dictionary does not
  contain. Together they test a whole candidate list in one pass, so a missing
  animation name never has to cost a relaunch.

- Story stealth has no universal detection meter. Sensory detection is
  range/FOV/LOS/event qualification plus `MovementDetectionTime`; witness
  suspicion is a readable accumulating/decaying motivation with thresholds;
  animals use separate threat events and unalerted/alerted/flee/attack tasks.
  `pedperception.meta` profiles are shared types, not one record per model.
  Crouch and `SET_PED_STEALTH_MOVEMENT` are separate states. Follow
  "Stealth and perception" above. The self-verifying neutral-observer runs
  measured a 55-60 degree perception-area edge at 15 m, separated crouch-walk
  noise from standing walk/run/sprint, and recorded an aiming-triggered threat
  response. They did not measure actual hostile notice/investigation/combat or
  how sight, noise, stance, light, distance and exposure time combine. They do
  not justify one universal stealth indicator or a completed stealth audit.
- Toxicity is ASI-managed through Rockstar's `SA_POISONED` ped attribute:
  confirmed Oleander consumption sets it to 100, configured Health Cures clear
  it, state persists, and damage is redirected to the outer Health bar over
  `[Toxicity] HealthBarDrainHours`. Native UI and double-drain remain TESTING.
- Temperature survival uses clothing-adjusted attribute 12 (0 cold, 50
  comfortable, 100 hot). Hot weather drains Stamina Core and cold weather
  drains Health Core according to `[Temperature]` INI settings; both are
  TESTING for native double-drain and outfit/region thresholds.
- Custom `LEX_INVENTORY_ITEMS.ytd` cartridge art is reserved for the six spent
  casing ingredient records. Loaded `AMMO_*` records retain their vanilla
  inventory/ammo-type icons; do not assign `LEX_AMMO_*` textures to them.
  The dictionary has been rebuilt and requested by GameplayTweaks; static audit
  confirms no loaded `AMMO_*` record uses it. Rendering remains TESTING.
- There is no proven native/data toggle for core reserve-bar behavior.
  GameplayTweaks approximates it with outer-ring checks, control/task blocking,
  and reserve-tick restoration. Player and horse core writes must use only
  Rockstar's direct `_SET_ATTRIBUTE_CORE_VALUE` path; `SET_ATTRIBUTE_POINTS`
  is progression state and mutates maximum outer bars. Horse Stamina latches at its visual
  floor and blocks further drain until release/recovery. Horse Health uses native
  point 100 as the empty outer-bar floor when max Health exceeds 100; reaching it
  kills immediately instead of spending the Health core. Dead Eye emptiness uses
  Rockstar's normalized `_GET_PLAYER_DEAD_EYE_METER_LEVEL(..., false)`, not raw
  `_GET_PLAYER_DEAD_EYE` points or a learned maximum. Empty Dead Eye stays latched
  disabled until it is inactive and the normalized meter genuinely refills above
  the configured cutoff. The latch uses the Dead Eye-specific disable native and
  never suppresses the shared special-ability inputs, because their non-aiming
  MMB context is Eagle Eye. Player sprint/bow/lasso/melee, Dead Eye, horse sprint/
  jump, and horse damage remain test-sensitive.
- No native or extracted tuning field directly controls the three core drain
  rates. CoreClock implements in-game-time drain and sleep handling in the ASI
  and is confirmed working. TODO #11 now has signed net points/second for player
  idle, walk/sneak, jog, sprint, swim and horse stand, walk, trot, canter, gallop,
  swim. A monotonic target controller owns the final per-tick result so native
  recovery and depletion cannot cancel each other. Runtime balance is TESTING.
- Ordinary Health, Stamina and Dead Eye XP awards converge on ped attribute
  indices 0, 1 and 2. Their cumulative thresholds are 0, 50, 100, 200, 350,
  550, 800 and 1100 points for base ranks 1 through 8. `[CoreXPGain] Enabled=0`
  captures the loaded save's three base ranks and refuses later increases; it
  does not reset existing ranks, alter current core fill, or touch bonus ranks.
- Wallet capacity is enforced by GameplayTweaks against the current Gambler
  challenge rank. `[WalletCap]` exposes `Rank0Dollars` through
  `Rank10Dollars`; zero means unlimited. Defaults are $1, $2, $4, $7.50,
  $12.50, $20, $40, $75, $150, $250 and unlimited. The cap is checked after
  the mask/fence cash multiplier so every positive cash source converges on the
  same final balance.
- Lexer confirmed in-game that the installed `CWeaponInfo.Speed` reduction
  makes firearm bullets definitely slower. `[ProjectileVisibility] Mode`
  defaults to `luminous_streak`: the ASI draws an adjustable incandescent
  world-space head and tail from the real held weapon's `Gun_Muzzle` along the
  synchronized firearm path. It never replays `core/bullet_tracer`, which is
  the same smoke-like effect already assigned by vanilla weapon data.
  `[ProjectileVisibility] Enabled=0` disables only the added renderer and
  leaves the 58 preserved vanilla tracer assignments as the sole path.
  Size, opacity, RGB, tail length/segments, maximum distance, light brightness
  and light range hot-read from `[ProjectileVisibility]`; `corona` retains the
  old single-blob fallback and `off` is a vanilla-only alias. Alignment and
  visibility remain runtime acceptance boundaries.
  `[ProjectileSpeed] GlobalFirearmSpeed` still requires the data-build helper
  and a restart; it is not a hot runtime setter.
- Empty bottles use Rockstar's existing `PROVISION_EMPTY_BOTTLE`, not a new
  `LEX_GLASS_BOTTLE`. The final-swig event precedes the measured discard by
  1.844 seconds; `[EmptyBottles] StowDelayMs` now defaults to 1450, cancels before
  release, removes the consumed source once, then grants after the satchel clip.
  Empty Bottle is in Materials with a five-item cap and explicit feed/count.
  `[EmptyBottles] HumanTonicBottles` controls all human tonic families. TESTING.
- Partial bounty payments are confirmed working in-game as of 2026-08-03.
  Technical row/databinding details remain in the owning issue worklog.
- Per-merchant BUYS overrides are tri-state in LEXEDITOR: Vanilla preserves the
  compiled category rule, Accept adds a PDATA exception, and Reject records
  `merchant_buy_overrides.csv`. During the shop-owned SATCHEL flow, GameplayTweaks
  matches active shop type plus `Global_1935689.f_10190` and greys/blocks the
  real Sell prompt for explicit rejects. Runtime behavior remains TESTING.
- Story Mode's gunsmith script recognizes `SHOP_BLK_GUNSMITH`, but the shipped
  persistent-character data only provides complete gunsmith owners and schedules
  for Valentine, Rhodes, Saint Denis, Annesburg, and Tumbleweed. Enabling a new
  town gunsmith therefore requires a physical shop/interior, persistent merchant
  and schedule, catalog interaction, blip, hours, and hostility/death recovery;
  it is not a dormant-shop toggle. Blackwater is the least speculative first
  port because its shop hash already exists.
- Radial mouse-wheel input and centre detection are confirmed, but the direct
  `SET_WEAPON_AMMO_TYPE` replacement is not: runtime readback remained on the
  old ammo type after every claimed selection. The only wheel-owned action is
  `INPUT_QUICK_SELECT_SECONDARY_NAV_NEXT/PREV`; any translation must be limited
  to a verified multi-ammo weapon, must leave the Items page untouched, and must
  verify the resulting ammo type before reporting success. The rejected
  `WM_INPUT` build broke mouse input; never restore process-wide raw-input
  registration.
- Disable-only greys masks; hide-only merely reduced the horse selector to one.
  Full-mask GUID moves into the ordinary bandana slot are rejected by
  `_INVENTORY_FITS_SLOT_ID`; do not retry them. Catalog-category rewriting also
  failed in-game and is reverted. "Inventory and radial architecture" above is the
  authoritative trace. `quickselectitems.ymt` maps item hashes to radial slot
  IDs: `KIT_BANDANA` uses `CLOTHING_ITEMS`; Story masks use
  `HORSE_LARGE_MASKS`. `short_update` separately queries the two catalog
  categories and calls `_INVENTORY_ENABLE_ITEM`/`_INVENTORY_DISABLE_ITEM`;
  those natives take an inventory ID and do not mutate a HUD collection.
  The installed approach removes all real bandana/Story-mask mappings, maps ten
  custom carrier records to `CLOTHING_ITEMS`, and keeps exactly one carrier in
  inventory for the persisted wardrobe choice. Carrier selection redirects to
  Rockstar's real mask/bandana interaction. Do not add F6. The 2026-07-30 live
  log proved both data replacements loaded. `InventoryGuid` must be four 64-bit
  `Any` slots (32 bytes), and the decompiled clothing grant path uses the
  `WARDROBE` container. The carrier now renders in the correct regular slot, but
  code marks it clothing-active every 500 ms, causing the permanent check mark;
  camp/task disabled-state gating is absent, and the latest log never observed
  the selected Black Hood. The follow-up observes the full equipped bitset and
  prioritizes newly rising wardrobe selections, mirrors exact worn state into
  clothing-active, and mirrors large-mask availability bit 8 into carrier
  enable/disable. Worn state, wardrobe changes, and greying remain TESTING.
- Kill/headshot Dead Eye refill has no identified removable data/native source;
  core-based regeneration is additive unless a hook is found.
- AnimPostFX effects can stack and expose strength; timecycle modifiers use one
  global slot. Ambient vignette removal is separate from low-core gameplay FX.
- CORE-EFFECT RAMP is dropped and disabled. Decompiled scripts and the complete
  public AnimPostFX native surface expose no callable equivalent of vanilla's
  engine-owned steady low-core activation. Manual play plus potency produces
  an unavoidable animated pulse. Do not reinstall it, revive the rejected
  generic vignette, or call it feasible without a new engine hook or extracted
  shader pipeline that can faithfully reproduce Rockstar's effect. The deferred
  installer moves any `CoreVignetteRamp.asi`/`.ini` found in the game root into
  `mod storage/CoreVignetteRamp`; it never installs that project.
- Resource-effect `percent` is the actual gameplay refill/loss. Integer `value`
  independently drives the coarse wheel preview: known-good horse remedies
  establish 25%=3, 50%=5, 75%=8, 100%=10, with 12.5%=1. Gameplay values do not
  need to use 12.5% increments; subtier values share a preview tier.
- `CONSUMABLE_SPECIAL_HORSE_STIMULANT_CRAFTED` is the one player-facing Special
  Horse Stimulant, not a second crafted variant beside a nonexistent
  `CONSUMABLE_SPECIAL_HORSE_STIMULANT`. Rockstar simply embedded `_CRAFTED` in
  its internal ID. Removing its `COST_CRAFTING_FIRE` acquire-cost removes the
  locked recipe entry; the pamphlet is an independent document record.
- A blipdata entry names a `<TextureDictionary>`. Story Mode rendered custom
  linkages in the separate `lex_blips` dictionary as black squares even when
  ScriptHook requested and kept it loaded. The attempted `blips` override was
  also rejected in the live Story configuration. All `LEX_BLIP_*` custom art
  therefore uses the proven complete `INVENTORY_ITEMS_MP` replacement: all 432
  Rockstar textures plus the entire custom map set. Never ship `lex_blips.ytd`,
  point a custom linkage back to it, or build a partial resident replacement;
  any of those actions regresses existing icons when a new texture is added.
  Replacing Lexer's custom icons with shipped Rockstar sprites is NOT an
  acceptable fallback and was rejected by him after being done unilaterally.
- Cigarette-card collectible blips use 144 set-and-card-keyed world-space X/Y
  coordinates. Do not derive them from website-map pixels or a global affine
  map transform: that path is far too inaccurate for a physical card. World
  Champions cards 2 and 11 intentionally share one coordinate because both
  pickups occupy the same shack windowsill. The native collectible-placement
  query does not expose usable cigarette-card positions.
- Development builds author persistent campsites by tapping F3 and remove them
  by holding F3 for 0.8 seconds while within the thirty-metre authored footprint,
  using `GameplayTweaks/campsites.csv`; release builds compile out the F3
  authoring input. Rockstar mission camps are separate
  script-owned camps and are not treated as authored sites.
  Nearby sites launch Rockstar's `player_camp` script at the saved coordinates,
  retaining vanilla camp interactions; sites have inactive/activated map
  placeholders, only activated sites are death-respawn destinations, and custom
  campsite glyphs remain TODO 186. Full camp launch, activation, map icons, and
  death respawn remain TESTING. Switching sites now sends cleanup flag 555 to the
  owned `player_camp` thread, waits for exit, and starts the requested coordinates;
  the old code incorrectly treated any existing camp thread as the new site.
  The saved campsite coordinate is the exact `P_CAMPFIRE02X_COMBO` origin, not a
  safe player spawn. Death respawn selects validated heading-relative ground at
  least three metres from that origin and never falls back to the fire coordinate.
  After Rockstar returns a live, controllable ped, the campsite transfer uses one
  instant-faded coordinate write and waits for collision without moving again;
  per-frame reassertion makes the gameplay camera fly across streaming origins.
- Animal density applies both the ambient-animal and scenario-animal per-frame
  natives. Obvious 0.1x/2.0x newly streamed population comparison remains TESTING.
- Owned-horse restart persistence records model, position, and heading every two
  seconds only after startup recovery has resolved. On the next Story load it
  reasserts the matching unmounted, unattached horse at that position during a
  bounded ten-second window, countering vanilla's startup relocation without
  moving the player or applying stale coordinates to a replacement horse.
- Surface-conforming climbing and prone remain ACTIONABLE. Reference exports are
  under `_analysis/reference-decompilation/`; parity checks are in
  `tools/reverse-engineering/verify_prone_climb_parity.py`. The latest climbing
  test found delayed movement animation, abrupt entry, no lateral traversal,
  hand clipping, and a shrub jump teleporting Arthur to an old barn anchor. The
  follow-up invalidates distant cached anchors, smooths a 320 ms authored entry,
  adds an authored lateral cliff-traversal loop with tangent movement and flank
  probing for corners, waits for the motion clip before translating, and applies
  dynamic hand-plane correction. All remain TESTING in irregular geometry.
  Prone weapon rigs based only
  on timed aim-sweep clips were rejected in-game: they did not follow the
  reticle and repeatedly rolled through terrain. They are disabled; binoculars
  yield directly to the existing native mode. Weapon selection/grounded combat
  remains ACTIONABLE; the installed follow-up ports the reference
  `prone_michael` wheel-close equip bridge. Tap-Ctrl now bypasses the rejected
  prone-to-knees clip and transfers directly to forced crouch.
- True plant spawn-density reduction remains unsolved. Do not reactivate the
  rejected scenario-point deactivation approach, which could leave visible but
  unusable plants.
- DS3-style overflow is actionable through an ASI-owned reserve, but not by
  merely watching rejected pickups: raise relevant engine caps so acquisitions
  enter inventory, observe the delta, keep active-cap quantity, and persist the
  excess. Every acquisition path and duplicated side effect still requires
  testing before the mechanism can be called universal.
- Custom challenge UI is visually feasible through native drawing, but seamless
  pause-menu interception/back navigation remains unproven.
- Recoverable unique weapons persist first acquisition and defer recovery while
  a matching live pickup exists; recovery, locker visibility, and duplication
  safeguards remain TESTING across all seven one-off hatchet/tomahawk variants.
- Hunter's Hatchet sets the struck ordinary free-roam animal to Perfect quality
  before killing the same ped. Mission/scripted animals are excluded and no
  replacement loot is granted. This remains TESTING.
- Cigarette-card resale uses twelve persistent mailed-set states. After a set's
  bundle and originals disappear through turn-in, later originals are converted
  to that set's `LEX_DUPLICATE_CIG_CARD_*` record, which fences accept. This
  remains TESTING; do not call turn-in detection confirmed until tested.
- RDR2 Native Menu Base is not a radial-menu library. It supplies vertical
  widgets plus arbitrary text/sprite drawing and keyboard/controller input;
  its README lists mouse support as unfinished. A radial wheel is feasible only
  as a new renderer/input widget we build on those primitives.
- The data-only any-order reference mod proves concurrent challenge roots can
  progress without a custom UI, but does so by creating one visible root per
  rank. This causes duplicate strand entries, inaccurate pause-menu progress,
  new-ID progress resets, and failures for some script-score goals. The planned
  runtime companion should preserve one visible strand while owning rank state;
  a custom UI is optional unless the vanilla page cannot represent it correctly.
- Runtime architecture decision (2026-07-16): reusable editor/runtime behavior
  belongs in optional `LexersLibrary.asi`; overhaul-specific behavior belongs
  in `Lexer's Mod.asi` (renamed from GameplayTweaks.asi). LEXEDITOR remains
  independently usable and must gracefully hide/disable runtime-only controls
  when the companion is absent.
- Binocular access reads physical keyboard Q and controller RB for the hold while
  leaving a tap as native Cover. A raise is rejected only while the actual Aim
  input/camera is active; the broad player-target predicate is not an aim gate
  because it can remain true after recon targeting ends. Retrieve/stow use
  Rockstar's locomotion-compatible swap task, and forced aim starts only after
  the draw task finishes. Both transitions remain TESTING.
- Plant world-model names ARE shipped: the decompiled scripts
  (`fm_mission_controller.c`, `net_gun_for_hire_offline.c`) enumerate the game's
  entire model index as `joaat("NAME")` literals — herbs included, as
  `S_<SPECIES>01X`/`S_<SPECIES>PICKED01X` and an abbreviated `<SPECIES>_P`
  family. Hashing those ~54k literals also reverses any unknown model hash to a
  name. Never again claim a model name must be guessed or learned by play
  without grepping that table first.
- Recon tagging is TESTING: the 2026-08-03 test used an installed INI with
  `[ReconTagging] Enabled=0`, so nobody—including the owned horse—was tagged.
  Both current INIs are corrected to `Enabled=1`, but require a fresh gameplay
  acceptance test. Physical keyboard Q and controller
  RB share one hold detector. A tap remains fully native Cover; only after
  `HoldMs` may the continuing Cover action be suppressed to open binoculars.
  Never synthetically replay a cover tap or derive the hold from disabled PAD
  state. Stable line-of-sight observation through binoculars or weapon aiming
  drives a continuous eight-corner projected-bounds threshold and a keyless
  `Studying` progress ring. Acquisition is automatic while the target continues
  to satisfy the reticle, range, projected-size, and line-of-sight gates; it has
  no second input because binocular targeting and weapon aiming share no tag
  control. Completion creates the session tag and,
  when the nonhuman target resolves to a real compendium entry, records the
  observation too. Ordinary humans and other entities without a compendium
  entry remain valid tag-only targets. The projected extent responds to target dimensions, viewing angle,
  distance, FOV, and zoom without animal-size buckets; model bounds are cached
  by hash. Tags anchor to the ped's head bone, with model bounds only as
  fallback. `StudyTimeMs`, `AimToleranceScreenRadius`, and
  `MinProjectedExtent` are hot-reloadable. The player's saddle horse is automatically tagged,
  uses the owned-horse minimap glyph, and hides its overhead tag while ridden.
  Tagged targets use a lower through-cover HUD marker, metre distance, a
  draw-budget-bounded layered health ring with 100 HP per color, and a retried
  entity-backed red/yellow/blue minimap blip. Recon validates compendium work
  with the same discoverable name/type and player gate used by Rockstar's
  `short_update`, defers the write outside the blip transaction, skips an
  already-observed target, and reads observed state back afterward. Marked
  blips use Rockstar's real `AUTO_MODIFIER_COP_SEARCH_CONE` heading modifier and
  follow target heading; multi-tag rendering, animal tagging, prompt presentation,
  the marker/ring, repeat click audio, and cone rendering remain TESTING.
  Outside missions, MarkedOnlyMinimap scans untagged human enemies, preserves
  law/mission entities, and removes entity-backed blips; tagged disposition is
  recomputed every frame so a newly hostile tag is rebuilt red. Whether every
  ordinary encounter dot is entity-backed remains TESTING.
- A world jump greater than 250 metres invalidates the shared global-ped snapshot
  and quarantines full-world ped scans, binocular entry, recon acquisition and
  stealth acquisition for five seconds. This prevents systems at the destination
  from mutating streaming-out handles cached in the previous region; a fresh
  snapshot is built after streaming settles.
- ScriptHook can start `GameplayTweaks` while the frontend/loading player has no
  control and before the live Story Mode ped is stable. `ScriptMain` may load
  files and initialize plugin-local state during that interval, but it does not
  query or mutate gameplay state. The runtime gate requires an existing, living,
  unfaded, controllable player ped for five continuous seconds, then seeds all
  delta-based baselines from that settled save before releasing feature updates.
- Rockstar can catch an internal failure, display `ERROR:FFFFFFFF`, and keep
  `RDR2.exe` alive. Windows then sees no unhandled exception, so WER and the
  plugin's vectored handler produce no dump. The external
  `tools/runtime/Capture-RDR2-ErrorDump.ps1` watcher detects the error window
  and calls `MiniDumpWriteDump` while the failed process is still alive,
  preserving full memory, handles, modules and thread state. A dump captured at
  that dialog shows Rockstar's main thread deliberately inside `MessageBoxW`
  after the ScriptHook fiber has yielded; it validates the delayed engine-abort
  shape but does not provide an exception stack naming the earlier bad native.
- Child target/damage rejection is engine-owned rather than controlled by the
  public targetability or entity-protection natives. Forcing child entity state
  permits an attempted hit to reach a bad engine path and causes
  `ERROR:FFFFFFFF`; child vulnerability never enumerates peds or writes entity
  damage, proof, invincibility, or targetability state.
- The established `Kill Children` v1.1 mechanism uses two internal predicate
  detours. A targeted flag-query detour returns false only for hash
  `0xE4401C70`; a second detour returns false for the child blood-effects
  predicate. Their call anchors are
  `BA 18 E6 A7 BA 48 8B CF E8 ?? ?? ?? ?? 84 C0 75 17` and
  `E8 ?? ?? ?? ?? 84 C0 75 78 48 3B 5F 08`. They exist once each in the
  current loaded `RDR2.exe` code but not in the encrypted on-disk bytes.
- GameplayTweaks resolves both calls inside the loaded `.text` section and
  installs the detours with MinHook. An atomic script-thread gate makes the
  detours forward to Rockstar's originals during missions, fades, loading,
  disabled player control, and custom menus, preserving scripted children.
  Build/static/signature validation is not in-game acceptance.
- A subsystem's final log record still does not identify it as the cause of an
  unrelated later asynchronous abort; use progressive update-boundary activation
  for failures that do not have a direct action reproduction.
- Owned-gear sparkle suppression is not present in the live update pipeline.
  Progressive staging independently reproduced Rockstar's delayed
  `ERROR:FFFFFFFF` after both the pickup-placement scanner and a guarded
  pickup-object scanner were activated, before child vulnerability ran. No
  individual native within that asynchronous window is recorded as the proven
  cause, and neither failed scanner is retained as a disabled runtime switch.
- The SDK declaration of `TASK::_GET_SCENARIO_POINT_CLOSE_TO_COORDS`
  (`0x345EC3B7EBDE1CB5`) does not establish its caller-owned output-buffer ABI;
  calling it from the ScriptHook C++ plugin corrupts the plant selector's stack
  and fails the compiler security cookie on return. Recon never calls this bulk
  native. Plant selection takes the asynchronous reticle ray's world hit and
  rate-limits `_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE` queries across the
  shipped WB_ harvestable type table, which returns one scenario-point handle
  without writing into a plugin-owned array.
- Story Mode suspends the ScriptHook script thread for the entire time the pause
  map is open. MAP can launch centered on the player when its focus is written
  once on the direct-map or pause-menu opening input edge, matching Rockstar's
  focus-then-launch transaction. Never poll or periodically refresh that focus
  while gameplay is running; the value is consumed only at frontend launch and
  periodic writes have no transaction owner. An ASI-script UiPrompt,
  MMB/R3 read, or live recenter call cannot run while that frontend owns the
  screen. The MAP UIApp exposes no script setter for the
  strength of one zoom step. Multiplying physical wheel/right-stick input only
  queues more ordinary steps; runtime testing produced equal-sized delayed zooms,
  stalls, and beeps instead of a stronger/faster step, so that injection and its
  setting are removed.
- Consumable horse-hunger balancing (Lexer, 2026-07-16): when an item also
  refills the player's Health Core, its horse Health Core refill must match the
  player's, not double it. Apples and carrots are the explicit exceptions.
  The reusable +6.25% horse-core effect is
  `LEX_EFFECT_HORSE_HEALTH_CORE_MINUSCULE` (`0x95E8D12A`); do not reuse the
  older zero-value `0xE6CED54E` record.

For experiments, prior failures and dated implementation history, search
`worklog/issues/` — recent work by issue number; older mixed material is in `worklog/legacy/`
section. Promote a fact up into this file only once it is settled and current.

- Lateral climbing: the game DOES ship an Arthur narrow-ledge locomotion
  set (mech_loco_m@character@arthur@terrain@unarmed@narrow_ledge, with
  _blizzard and _cliff variants). An earlier note claiming no lateral
  animation exists anywhere was wrong. Story Mode scripts never set
  movement clipsets in RDR2, so it must be played as an anim dictionary.

- Shell-eject VFX (#85a): VERIFIED 2026-08-05 across the whole shipped
  weapon stack - base weapons.ymt (54 vanilla effects, all blank) and all
  six per-weapon patch ymts (m1899, evans, lemat, gambler DA, navy,
  elephant - all blank). There is NO live vanilla shell effect anywhere in
  what ships, so a duplicate casing cannot come from that source and #87
  does not block it. Note VfxWeaponShellInfoHashName is nested under <Vfx>,
  not a direct child of the weapon Item; a direct-child search finds zero
  and reads as 'no data'.
- UWO is incompatible with this overhaul's Story shop owners. With UWO loaded,
  shop icons and clerk interactions can disappear. Keep `UWO.asi` disabled.
- `Global_1430252` is Rockstar's private newspaper-shop availability cache.
  `shop_newspaper_boy.c::func_564` owns its refresh and three buckets. An
  unrelated ASI loop must not copy that refresh or write the cache: doing so
  invalidates live shop volumes, cycles shop state, and applies the LOCKED
  presentation state across shop families. Conditional newspaper markers count
  state-zero entries directly from the 14 persisted `Global_40.f_9479` records
  into local storage and never read or write `Global_1430252`.
