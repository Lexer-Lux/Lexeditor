# Worklog: 024 Follow Up Candidate Build 2026 08 03

## Follow-up candidate build — 2026-08-03

- #1: horse exhaustion now latches on the first core decrement while sprint is
  held and outer Stamina is below 16%, restores the previous protected core,
  and pins it until sprint release plus 2% outer recovery.
- #7: applies both `_SET_AMBIENT_ANIMAL_DENSITY_MULTIPLIER_THIS_FRAME`
  (`0xC0258742B034DFAF`) and `_SET_SCENARIO_ANIMAL_DENSITY_MULTIPLIER_THIS_FRAME`
  (`0xDB48E99F8E064E56`).
- #11: `StaminaRateController` uses signed points/second and a monotonic target
  for player idle/walk-sneak/jog/sprint/swim and horse stand/walk/trot/canter/
  gallop/swim. It corrects the observed bar to one owner per tick.
- #42: scans all mask equipped bits without stopping at the first worn mask,
  prioritizes newly rising wardrobe selections, mirrors exact worn state into
  clothing-active, and mirrors large-mask availability mask 8 into carrier
  enable/disable. quickselect slot and catalog category remain independent.
- #59: a requested campsite no longer adopts an unrelated running camp. The
  owned `player_camp` thread receives cleanup 555; after exit, the script starts
  the requested saved coordinates. Duplicate radius is 10 m and removing the
  materialized site also cleans its thread.
- #103: the live trace measured 1.844 seconds from final swig event 442509369 to
  discard. Default `StowDelayMs=1450` leaves most of that authored drink, cancels
  before release, removes the consumed source once, then grants after the satchel
  clip. Empty Bottle is a Materials item with visible icon/feed and cap 5.
- #112: mode `engine_tracer` writes `VfxWeaponTracerInfoHashName=0xD5551261`
  into every firearm CWeaponInfo modified by the speed helper. `corona` retains
  the rejected synthetic effect as fallback; `off` disables visibility changes.
- #113/#167: recon is enabled in both INIs. Outside missions, untagged non-law
  enemy entity blips are removed; tag disposition is recomputed every frame so
  neutral-to-hostile transitions rebuild immediately as red.
- #116: removed the secondary-task clear and obsolete SkipAnim setting. Forced
  aim waits 650 ms for Rockstar's binocular draw; release waits 700 ms for its
  stow before restoring the previous weapon.
- #144: rebuilt `LEX_INVENTORY_ITEMS.ytd` (963105 bytes) and explicitly requests
  that dictionary. Static catalog audit shows zero loaded `AMMO_*` records use
  it; the six `LEX_CASING_*` records do.
- #146: LEXEDITOR BUYS is tri-state. Accept updates the sparse PDATA list;
  Reject records `merchant_buy_overrides.csv`. Shop scripts expose active shop
  type in `Global_1914319.f_16855.f_34`; the sale satchel exposes selected item
  in `Global_1935689.f_10190` and its real PromptSelectEnabled DataBinding ID at
  `Global_1935689.f_10214`. Explicit rejects grey/block `INPUT_SHOP_SELL` there.
- #166: disabled both failed streamed `blips.ytd`/`lex_map_icons.ytd` overrides
  recoverably and maps added categories to distinct resident Rockstar sprites.
- #169: cache invalidates when the ped moves away, entry smoothsteps for 320 ms,
  authored `script_story@fus1@ig@ig_1_cliffsidetraverse` supplies lateral motion,
  flank probes wrap corners, translation waits for its clip, and hand-plane
  correction keeps hands outside the surface. Static parity verifier passes 32.

All items above remain runtime acceptance work; compile/static/deployment proof
is not a claim that the player-visible behavior has passed.

