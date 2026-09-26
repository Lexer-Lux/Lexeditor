# GF acquisition in battle (FF8_EN.exe 064d466b)

Proven statically against the Steam 2013 EN executable.

- GF owned: byte `01CFDCB9 + GF × 0x44`, bit 0 (the GF record starts at
  `01CFDCA8`). `0047E480(gf)` sets it; nothing else about the GF changes.
- Drawable GFs sit in the enemy's Draw list as `0x40 + GF`. Each of up to eight
  enemies has four entries at `01D28F18 + enemy × 0x47 + entry × 4`; the enemy
  is present when byte `01D2885C + enemy` is non-zero. An empty entry is 0.
- Battle setup `0048BA10` loads every enemy, Draw lists included, before
  `0048BB87`.
- The battle-end reason byte is `01CFF6E7` (1/3 game over, 2 escape, 4 victory,
  5 other). Victory is written at `0048655F`.
- GFs gained in a battle are listed at `01CFF6E4` (three bytes, `FF` = none;
  count at `01D28E17`). The post-battle flow reads the list at `00470BA9` to
  show the "GF acquired" screen. Both the Draw command (`0048D67D`) and the
  enemy-AI award (`00489E1C`) call `0047E480` and then append to the list.
