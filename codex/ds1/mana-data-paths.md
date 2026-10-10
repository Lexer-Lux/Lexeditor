# DS1 mana data paths

Verified against the installed Remastered `GameParam.parambnd.dcx`
(141 Magic rows) with the repo's own parsers. Foundation for #742.

## Magic.mp: the per-spell mana cost override

- `Magic.mp` (s16, 0-9999) is 0 on all 141 vanilla rows. The unmodded
  game has no mana pool and ignores it, so writing it preserves
  vanilla behavior.
- Contract: the Mana tweak reads `mp` as this spell's mana cost per
  cast. `mp` 0 means no override: the tweak derives the default cost
  from usages instead.
- The Spells tab exposes it as "Mana cost override"
  (`plugins/ds1/metadata/annotations/MAGIC_PARAM_ST.json`).

## Magic.maxQuantity: the N in X/N

- `maxQuantity` (s16) is the spell's cast count: Soul Arrow 30, Great
  Soul Arrow 20, Soul Spear 4, Combustion 16, Fire Surge 80.
  Dummy rows hold -1.
- The Mana tweak derives a spell's default mana cost as `X / N`,
  where `X` is the tweak's global conversion setting and `N` is this
  value.

## Magic.stamina

- 0 on every sampled vanilla row. Spells cost no stamina unmodded.
