# #519 — Create Theme

## State (2026-09-23 per-game-ff7r pass)

- Source already present: `games/ff7r/theme.py` (plugin-local dark blue/cyan
  glass-HUD fallback theme; private installed-theme asset pipeline confined
  to the user-data cache; documented `SystemFontNormal4K` bitmap-font path
  decodes locally with no Square Enix data committed; shared UI sound slots
  wired with direct browser-ready installed audio; cooked menu audio stays
  discovery-only until a validated SoundWave decoder exists). Provenance and
  rights recorded in `games/ff7r/THIRD_PARTY.md`.
- Tests: `tests/test_ff7r_theme.py`, `tests/test_ff7r_bitmap_font.py` pass
  (full ff7r selection: 519 passed). No code change needed on this branch.

## Needs Lexer (installed game + rendered UI)

- Inspect rendered and installed-game appearance; extract proprietary assets
  only from the local installed game; confirm the fallback stays usable where
  installed assets cannot be decoded safely.
