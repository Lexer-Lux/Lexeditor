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

Separate in-game SFX/Music sliders need two halves: a Config-menu
replacement (game-side mod, needs in-game proof) and backend consistency
(Lexeditor writes the two gains into `FFNx.toml` on deploy —
`set_audio_volumes` in `plugins/ff8/ffnx_manager.py`, `None` preserves the
existing key so `-1` auto-detect survives when a side is unmanaged).

## Editor half (landed)

- The Tweaks page has SFX VOLUME and MUSIC VOLUME rows (0-100, bounded
  number controls with a `%` unit). An unset side shows 100 without arming
  the gain; touching a slider stores a real gain.
- Gains persist per mod as `sfxVolume`/`musicVolume` in
  `lexeditor-settings.json` (`None` = unmanaged) and are applied to
  `FFNx.toml` on launch via `gameplay_settings.save(..., install_runtime=True)`.
- Covered by `tests/test_ff8_audio_volumes_issue_498.py` (validation,
  load round-trip, save persistence, per-key FFNx.toml writes, editor
  slider presence).
- Still game-side: the in-game Config-menu slider replacement and audible
  isolation/persistence proof.
