# DS1 mana data paths

Verified against the installed Remastered `GameParam.parambnd.dcx`
(141 Magic rows) with the repo's own parsers. Foundation for #742.

## Magic.mp: the per-spell mana cost override

- `Magic.mp` (s16, 0-9999) is 0 on all 141 vanilla rows. The unmodded
  game has no mana pool and ignores it, so writing it preserves
  vanilla behavior.
- Contract: the Mana tweak reads `mp` as this spell's mana cost per
  cast. `mp` 0 means no override: the tweak bakes that spell's Dark
  Souls 3 FP cost instead.
- The Spells tab exposes it as "Mana cost override"
  (`plugins/ds1/metadata/annotations/MAGIC_PARAM_ST.json`).

## Magic.maxQuantity: the N in X/N

- `maxQuantity` (s16) is the spell's cast count: Soul Arrow 30, Great
  Soul Arrow 20, Soul Spear 4, Combustion 16, Fire Surge 80.
  Dummy rows hold -1.
- Superseded for defaults by the #923 ruling (Dark Souls 3 FP costs,
  not X / N); the counts stay the vanilla reference.

## Magic.stamina

- 0 on every sampled vanilla row. Spells cost no stamina unmodded.

## The only usage-modifying effect: stateInfo 194

- Of all 850 SpEffect rows, exactly one carries stateInfo 194
  ("Increase number of magic uses"): row 2060, the Dusk Crown
  Ring's effect (Accessory 116, refCategory SpEffect).
- Row 2060's only other functional field is maxHpRate 0.5. There
  is no magnitude field for the cast-count change, so the halving
  (and any damage change) is keyed off 194 in code.
- For the mana tweak: when stateInfo 194 is active, scale mana
  costs instead of halving counts. No param field in Magic,
  SpEffect or Accessory accounts for attunement copies either, so
  that multiplication also lives in code.

## Spell description text path

- `msg/ENGLISH/item.msgbnd.dcx` ships `Magic_description_.fmg`
  (67 filled) and `Magic_long_desc_.fmg` (72 filled) next to
  `Magic_name_.fmg`, all keyed by Magic row ID (3000 Soul Arrow's
  short text is "Fire soul arrow") and parsed by the repo's own
  FMG reader. The tweak rewrites these entries for mana wording;
  `texts.py` currently handles names only.

## CalcCorrectGraph: how the game reads scaling graphs

- Verified 2026-10-11 against the installed params plus the wiki's HP
  table (http://darksouls.wiki.fextralife.com/HP). Row 100 (Max HP):
  stages 1/15/30/50/99, growth 400/682/1100/1500/1900, exponents
  1.1/1.2/-1.2/-1.1/1.0.
- Growth values are absolute stat values, not percents. Below the
  first threshold the value is the first growth; above the last, the
  last growth. Between thresholds the span position bends by the
  starting stage's exponent (1 linear, 2 quadratic, negative flips
  the axes: steep early, flat late).
- The formula reproduces every HP stage boundary exactly and every
  wiki midpoint within 2 (per-level rounding or wiki noise).
- Row 101 is unused by the game (leftover data, no reader). The Mana
  tweak owns it as Max MP (Attunement), renamed in row_names.

## HUD bars: how the game draws them

- Verified 2026-10-11 against the live heap. The F20-00 HUD bars are
  sprites (plate, two fills, frame), 13px tall. F20-00 also carries
  dead Demon's-Souls-era MP nodes (mg_plate_mp, mg_bar_0/1/2_mp, Null
  shape, parked off-screen) plus an off-screen MP icon.
- Bars render from 80-byte heap items holding tint, UVs and the rect
  as floats; each item's node (a parallel 64-byte entry) points at
  it from node+0x20.
- Node properties go through a vtable call at +0xD8 with numeric IDs;
  bar construction sets 2000/2002/2004/2008. Property 2004 is the fill
  fraction, set as {float value, int 1} (1.0 preset at build).
- Each HUD bar is a FrpgMenuDlgObjSmoothGauge widget: a factory call
  (0xEE0820, parent/label/node-name/class-name) plus an attach call
  (0xED6020, dialog/node-name) per bar. Only bar_0_hp is named in code
  (creation plus the 0x67B270 and 0x6F5D10 finders); siblings follow by
  structure. Fill renders through vertex quads (right edge, three
  buffers); driving property 2004 moves them, so the tweak never
  touches quad memory.
- Tint bytes rotate left one place between the menu file and memory
  (filed ff ff 78 1e reads ff 78 1e ff); memory order is red, green,
  blue, alpha. Vanilla fills are white; bar color comes from the
  texture strip each node samples.
