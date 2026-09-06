# Enemies UI and private card previews

- Scan remains `enemies.rows[].scanDescription` and is saved through the
  existing Scan pipeline. Its control lives in Battle Text, including for
  enemies without local scripted dialogue.
- Draw/Mug/Drop display one row per level tier and edit the original entries.
  All four stored slots and both bytes per entry are preserved; Draw hides
  slot labels, but does not reorder, merge, or delete slots.
- Defence toggles use the existing DAT conversion in `enemy_tables.py`:
  element percentage = 900 - 10 * byte, status percentage = byte - 100.
  Element immunity is exactly 0%; status immunity is 155% (byte 255).
  Other values, including negative element values, remain separately editable.
- Card choice 255 is the existing schema's Immune sentinel; it has no picture.
- `card_art.py` reads the supported English EXE's embedded cards TIM, privately
  and in memory. Layout source: FFNx c056db2783f376a340fcefa6a48cc33618998876,
  `src/ff8_data.cpp` (TIM pointer), `src/ff8/vram.cpp` (cell/CLUT addressing).
  The executable hash is checked before interpreting fixed offsets. Neither
  the EXE nor generated art should be committed or distributed.

Regression entry points: `tools/verify_ff8_enemy_compact_ui.py` (real UI with
synthetic data), `tools/verify_ff8_card_art.py` (decoder and HTTP route).
Both optionally accept `--exe` for privately checking installed card art.
These tests do not replace acceptance in the user's running editor.
