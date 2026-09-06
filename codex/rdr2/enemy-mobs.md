# Enemy accuracy, health and the Mobs tab

Enemy "stats" are three unrelated layers. Nothing in the data joins a ped model
to a profile or an archetype — that binding lives in dispatch specs, scenario
data and script — so no editor view may invent one.

### Base accuracy is per faction

`update:/common/data/ai/combatbehaviour.meta` holds 40 `CCombatInfo` records
under `CombatInfos`, each with its own `WeaponAccuracy`. `PLAYER` is `0.1`;
`GANG_ODRISCOLLS` is `0.6` with `CombatAbility CA_Professional`. Names are a
mix of shouting and mixed case in the same file (`LAW_UNSKILLED` beside `Law`,
`LawMarshal`, `Guard_Unskilled`, `RoughTraveler`); match them exactly. Only two
records are non-human: `COMBAT_ANIMAL` and `COMBAT_ALLIGATOR`.

### The situational stack is global, and it is what makes enemies miss

`update:/common/data/ai/pedaccuracy.meta` has exactly two profiles, `companion`
and `Default`, and multiplies the base value above. In `Default`,
`AI_TARGET_MOVEMENT_LATERAL_MODIFIER` is `0.5` and
`AI_TARGET_MOVEMENT_AWAY_MODIFIER` is `0.4`. These key on movement DIRECTION
with no speed threshold anywhere in the group, so a walking target claims the
same penalty as a sprinting one. The only compensation is the
`AI_TARGET_LOITERING_*` ramp, which requires the target to be loitering
(`AI_TARGET_LOITERING_TIME_OUT_OF_COVER` is 6 s), so continuous walking
suppresses it indefinitely. A 0.6 faction fights at an effective 0.3 against
anyone who keeps walking. This is authored behaviour, not a mod regression, and
it is not related to projectile speed.

### Health is per archetype

`update:/common/data/pedhealth.meta` — `HealthConfig` (per-archetype
`DefaultEnergy`, armour, injury/critical/writhe thresholds, melee fatigue and
knockout thresholds, fire vulnerability), plus `StaminaConfig`,
`SpecialAbilityConfig`, `HealthRechargeConfig` and `EnergyConfig`, the last of
which binds an archetype to its health/stamina/special-ability records. The
`HEALTH_ENEMY_EASIEST..HARDEST` and `HEALTH_LAW_*` ladders are the difficulty
tiers. The mod does not ship this file until the first Mobs save, which copies
the vanilla extract in and adds the `install.xml` mapping.

### The model -> archetype binding is not in any data we have

Proven by exhaustion, not assumed: the `HEALTH_*` archetype names appear nowhere
in the entire extract set except `pedhealth.meta` itself, and only six times in
the whole decompiled SP script set (`_SET_PED_HEALTH_CONFIG` in `gang3` and
`odriscolls4`). There is no getter native for a ped's health config either — only
`_SET_PED_HEALTH_CONFIG` (`0xF6B82FCE03B43A37`) exists.

Consequences that must not be re-litigated:

- No editor view can show "this ped model's health" from data. It can only show
  what a runtime probe observed, and it must say which it is doing.
- Observed max health does not uniquely identify an archetype: 37 archetypes
  share 21 distinct `DefaultEnergy` values. Show every candidate; never pick one
  silently.
- Assigning an archetype to a model is a RUNTIME override, written to
  `GameplayTweaks/mob_archetype_overrides.csv`, in the same shape as
  `merchant_buy_overrides.csv`. There is no data field to write instead.
- Mission-scripted enemies set their own config at spawn, so last writer wins;
  an override may lose to a mission script.

### The enemy difficulty ladder is a naming convention, not a stat ladder

`HEALTH_ENEMY_MEDIUM`, `_HARD`, `_HARDER` and `_HARDEST` are identical in every
field (70 energy, injured at 49). `HEALTH_ENEMY_EASY` is the toughest of the six
at 75. Only `HEALTH_ENEMY_EASIEST` (50) genuinely differs. Whatever separates a
hard encounter from an easy one, it is not health — look at the combat profile,
the loadout and the combat style instead.

Likewise among the six archetypes at 75 energy, `HEALTH_ENEMY_EASY`,
`HEALTH_LAW_EASY` and `HEALTH_LAW_MEDIUM` are byte-identical to each other.

### Editor ownership

The Mobs tab serves `/api/mobs` and `/api/mobs/save`, splits Humans / Animals
by record name, and offers two views: Combat profiles and Health archetypes.
Its help text must keep saying which layer owns accuracy; an earlier version of
this project asserted that enemies have no per-faction accuracy, which is false.

`save_file` rewrites through ElementTree, which normalizes duplicated spaces
before an attribute (`<Tag  value=` becomes `<Tag value=`). Expect cosmetic
diff noise on `combatbehaviour.meta`; it is not a value change.

