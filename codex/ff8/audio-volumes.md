# FF8 audio volumes (issue #498)

## Vanilla behavior

- The in-game Config menu has one Sound slider. It drives SFX-ish gain;
  players report it does not turn down the music.
- Lexeditor reads that single value as the `Volume` config field
  (`plugins/ff8/init_data.py`).

## FFNx backend (pinned release 1.24.3, `misc/FFNx.toml`)

- `external_sfx_volume` and `external_music_volume`: `0..100` gains for the
  SFX and Music layers. `-1` means auto-detect, which on FF8 (2000 and Steam)
  is always 100% — the game's own Sound slider does not feed these keys.
- The gains govern the external layers (`use_external_sfx`,
  `use_external_music`). Whether they affect vanilla audio with the layers
  off is unproven; that needs an in-game check, not CI.
- Voice/Ambient have their own layers and gains; out of scope for #498.

## Implication for #498

Separate SFX/Music sliders belong in the game's own Config menu (below),
not on Lexeditor's Tweaks page: Lexeditor does not write these FFNx gains.

## In-game Config menu (verified statically against FF8_EN.exe 064d466b)

- The Config menu is table-driven: 16-byte rows at `00B88970` (+0 label text
  id, +2/+4 option text ids, +6 type, +8 config-byte offset or flag mask,
  +0xA cached slider position written at runtime, +0xC callback), ended by an
  FFFF row. The row count is computed from the terminator (`01D8D440`).
- Type 0x21 is the 0-100 volume slider; types 3-5 are 5-step sliders. Sound is
  text 0x35, type 0x21, config byte 3; changing it calls
  `sfx_set_master_volume` (`0046A390`).
- Labels are menu text bank 2 through `004BD630(1, 2, id, 0)`; help is
  `(1, 2, id, 1)`.
- Music: `0046C6F0(volume 0-127, fade)` stores the target in `01CD24E4` and
  drives DirectMusic. FFNx calls this `master_midi_volume`.
- The save's config block (20 bytes at `01CFE738`) has no free byte.
