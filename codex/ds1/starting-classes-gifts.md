# Starting classes and starting gifts (CharaInitParam)

`CharaInitParam.param` in `param/GameParam/GameParam.parambnd.dcx` holds who
the player begins as and what each gift grants. 314 rows, 240 bytes each,
`CHARACTER_INIT_PARAM`, header version 2. All of the below was decoded from
the shipped archive and cross-checked against starting values.

## The live rows

- Rows 3000-3009 are the ten starting classes in class order: Warrior,
  Knight, Wanderer, Thief, Bandit, Hunter, Sorcerer, Pyromancer, Cleric,
  Deprived. They hold complete kits: stats, soul level, weapons, armor,
  ammunition, rings, attuned spells, items with counts, souls, gestures.
- Rows 2401-2408 are the eight gifts in gift-menu order: Goddess's
  Blessing, Black Firebombs, Twin Humanities, Binoculars, Pendant,
  Master Key, Tiny Being's Ring, Old Witch's Ring. Each grants its goods
  from its item slots (Blessing x3, Firebombs x10, the rest x1) or its
  first ring slot. The ninth gift, None, is no row.
- Rows 2000-2009 mirror the classes byte for byte except the right-hand
  weapon, the left-hand weapon (a hilt and empty), and the draw type
  (ghoul body instead of none). Editing a class writes both rows so they
  can never drift apart; the draw type is left alone. Whether the 2000s
  are stale or a hollow form is not settled; mirroring is correct either
  way.
- The other rows are development snapshots, title-screen builds, face and
  body presets, and NPC loadouts. The editor lists only classes and gifts.

## Field notes

- The stat byte at offset 203 is Resistance, verified for all ten classes
  against published starting values (Thief 10, Sorcerer 8). Community
  paramdefs mislabel it baseDurability; the name is kept as the storage
  key, and the editor labels it Resistance.
- The two bytes before it (offsets 201-202) read 10 and 0 on every class
  and vary on other rows. Their effect is not documented, so the editor
  shows them read-only as unknown values.
- Empty slots read -1 on class rows and 0 on gift rows; the game treats
  either as empty, and the editor shows both as None.
- `vowType` is the starting covenant, 0-9, verified against the online
  check rows 3-12: None, Way of White, Princess Guard, Warrior of
  Sunlight, Darkwraith, Path of the Dragon, Gravelord Servant,
  Forest Hunter, Blade of the Darkmoon, Chaos Servant.
- `npcPlayerSex` is 0 for female and 1 for male, verified on the male and
  female face rows 2300-2319 and three named NPC rows.
- `npcPlayerDrawType` follows the NPC draw enum: None, White Phantom,
  Black Phantom, Intruder, Ghoul Body.
- `equip_Skill_01-03` are unused (always -1 outside gift rows, which
  store 0). The three `QWC` halves are 0 on all 314 rows.
- `soulLv` ranges 0-9999, stats and item counts 0-99, gestures -1 to 127.
