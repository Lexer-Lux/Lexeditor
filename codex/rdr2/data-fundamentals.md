# Data fundamentals

- LML loads XML replacements through `install.xml`.
- Catalog prices are cents in `catalog_sp.ymt`.
- Consumable effects are catalog effect references plus shared effect records.
- Loot uses `loot_table_*.meta`; skinning uses `loot_items_matrix.meta`.
- Challenges use `challenges_sp.meta`, `goals_sp.meta`, and localization.
- OpenIV's PSO exports contain unresolved JOAAT hashes. Preserve structurally
  verified field names; do not guess unknown hashes.

### Localization

Catalog `ui/key` and `ui/description` point to real localized text. LEXEDITOR
edits those strings through `strings.gxt2`. `install.xml` must map
`strings.gxt2` explicitly. Missing descriptions may be created and attached to
the catalog item. Text changes require a game restart.

LML localization keys must be either symbolic identifiers or exactly
`0x` plus eight hexadecimal digits. Never append suffixes to a hash (for
example, `0x98890653_DESC`): LML throws while parsing it and then abandons the
entire mod installation, including every unrelated file replacement. For a
hashed catalog item with no description, LEXEDITOR uses
`LEX_DESC_<8-digit-hash>` and validates every key before writing.

Consumable wording uses these design meanings:

- Health Core = hunger
- Stamina Core = thirst
- Dead Eye Core = wakefulness

Do not call core filling health/stamina/Dead Eye restoration; reserve those
terms for outer bars. Mention horse benefits when applicable.

Consumable magnitudes use: 6.25%=marginal, 12.5%=slight, 25%=modest,
37.5%=moderate, 50%=considerable, 62.5%=substantial, 75%=great, and
100%=complete. Preserve the rigid standardized tier lines for generic Health,
Stamina, Dead Eye, horse Health, horse Stamina, and Miracle Tonics; other
consumables, including tonic-like items, use natural item-specific prose.

### Effects

An effect has two game identifiers:

- Catalog effect key: referenced by items, often stored as a JOAAT hash.
- Behavior ID: selects an existing engine operation.

Editor labels and `LEX_EFFECT_*` symbols are organizational metadata in
`editor/labels.json`, not additional engine identifiers. New effects may use
new keys and magnitudes but must select an existing Behavior ID. Effect records
must remain sorted by numeric key; LEXEDITOR canonicalizes and sorts them when
saving. `value`, `time`, and time units are integers; `percent` may be decimal.
Plain `EFFECT_HEALTH`, `EFFECT_STAMINA`, and `EFFECT_DEADEYE` use integer
`value` as the real outer-bar point change. Core and horse-resource behaviors
instead use decimal `percent` as the gameplay magnitude and integer `value` as
their coarse inventory/wheel preview tier.
For persistent catalog effects, `timeunits=2` means in-game hours and
`timeunits=3` means in-game days. Thus `36/2` is 36 in-game hours and `1/3` is
one in-game day; do not label these as real-time minutes or hours.

### Shops and acquisition

- A catalog buy price does not list an item in a shop.
- Catalog buy price and purchase output are global per item; individual shop
  listings control only membership and availability requirements.
- `shopsinventories` controls what shops sell to the player.
- A `SELL_SHOP_DEFAULT` cash record controls global sellability and payout.
- PDATA `0x0BA63B3D.ymt` is not a complete player-to-merchant acceptance
  whitelist. Its sparse, ammo-heavy lists are explicit exceptions; normal
  acceptance is decided by compiled shop category rules. The trapper PDATA list
  contains no pelts or carcasses despite accepting both in game.
- Runtime loading must use the literal parsed-data resource hash `0x0BA63B3D`,
  not joaat(`PDATA_SHOP_INVENTORIES`) (`0xA84503E1`). The ASI retries capture
  after Story Mode initializes; LEXEDITOR enables merchant toggles once the
  resulting vanilla baseline has been imported.
- Purchase quantity comes from the acquire-cost yield; requirement counts are
  separate availability metadata.
- Item Sources indexes shops, recipes, direct and nested loot paths,
  ped/container/plant/reward pools, skinning, challenge rewards, known fixed
  collectible coordinates, and symbolic plus signed/unsigned-JOAAT references
  across the complete decompiled Story-script corpus. Rebuild the persistent
  script index with `python tools/build_item_script_provenance.py` when that
  corpus or catalog changes. Script hits remain candidates or incidental clues
  unless the acquisition path is independently confirmed. Engine-only dynamic
  grants remain partial, so “possible cut content” must remain false until that
  final coverage gap is resolved.

### Carry caps

- Multiplicity rows are context contributions, not always final capacities.
- `SLOTID_ANY`: fallback context. `0` contributes nothing; `-1` means no numeric
  catalog cap in that context, not necessarily practical infinity.
- `SLOTID_SATCHEL`: base satchel contribution.
- `0x04718245`: Legend of the East satchel contribution.
- `0xE655E53D` and `0xD4774180`: cumulative ammunition upgrade contributions.
- `0x550898DE` and `0xAEEE1782` remain unresolved; never invent labels.
- Thrown weapon-instance records have multiplicity 1. Their usable capacity is
  on the corresponding `AMMO_*` record.

### Weapons and ammo

`weapons.ymt` is layered. `CAmmoInfo` stores shared ammo behavior; each weapon's
ammo-keyed `DamageInfos` stores actual damage, penetration, accuracy, falloff.
High Velocity range comes from falloff curves. Radial stat bars summarize those
fields; they are not a separate authoritative table.

**SETTLED (2026-07-20): weapon data is a STACK.** base `weapons.ymt` + per-weapon
override ymts in `pack_patch/` (m1899, evans, lemat, gambler DA, navy, elephant)
+ `weaponcomponents.meta` layers = 11 files. Replacing ONLY the base file reverts
Rockstar's own weapon patches; repeater double-fire, lantern pose and missing
off-hand holster are the game's PRE-PATCH behaviour, not corruption or a parsing
failure. Proven by A/B: a byte-vanilla base with only shells blanked reproduced
them as soon as an `install.xml` entry loaded it, and removing the entry fixed
them. Serialization, line endings and unresolved hashes were all red herrings.
LML does NOT auto-load `weapons.ymt` without an `install.xml` entry.

- Editor policy (`server.py` WEAPON_STACK): weapons edits are refused until all
  11 stack files are present in MyOverhaul; all 11 are present and mapped.
- The three patch component layers (`patch_`, `003_`, `004_`) entered the
  repository from fresh OpenIV game exports. Their unresolved hashed tags were
  mechanically named from known schemas without copying reference-mod values.
  `003_weaponcomponents.meta` being byte-identical to Weapon Rebalance's copy
  means that mod shipped the vanilla layer unchanged; it is not evidence that
  this project copied the mod. No clean-baseline extraction remains.
- Shell-VFX blanking is verified across the complete shipped stack; see the
  current Shell-eject VFX finding near the end of this file.
- Extraction: RPF8 CLI (`_downloads/RPF8_TOOL`) cannot parse the nested
  update-content archive (`0x800AFF13.rpf` inside `update_2.rpf`). Use OpenIV
  with the game closed for the pack_patch files.
- LEXEDITOR resolves these OpenIV-unresolved type hashes before saving:
  `0x072C658E`=CRumbleInfo, `0x867DEDAF`=CWeaponDegradationInfo,
  `0xB0FF7A4C`=CWeaponDamageFallOffInfo, `0xCFEE9058`=CVehicleWeaponInfo, plus
  18 inner fields (falloff distances, degradation, rumble phases, vehicle
  kickback). Confirmed by matching vanilla records against two working weapon-mod
  schemas; no reference-mod values copied.
- `ProjectileFlags` is a mixed bitset representation: readable enum names and
  raw `0x...` tokens identify hashed flags, while
  `{BITSET,UNKNOWN_BIT_INDEX:N}` preserves an unresolved bit position. Never
  re-export it through a schema that drops unknown bits. The shipped base file
  must retain every vanilla projectile token; `tools/check_weapon_flags.py`
  enforces that invariant and LEXEDITOR refuses a weapon save when it fails.

### Challenges

- `goals_sp.meta` defines counters, conditions, targets, and reset windows.
- `challenges_sp.meta` defines strands, rank order, and rewards.
- Multiple score-source Items are independent counters; removing one deletes
  its complete child Item.
- Challenge-gated shop stock uses `CUnlockReward` plus shop membership.
- Data-only Series/Parallel conversion is disproven. Splitting ranks creates
  duplicate menu entries.
- The pause menu hardcodes nine top-level strands. A tenth data root loads but
  does not appear. More strands require the planned ASI-owned Challenges UI or
  repurposing an existing slot.

