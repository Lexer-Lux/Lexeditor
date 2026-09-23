# #524 — FF9 theme

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/524)

## 2026-09-23 — per-game-ff9: system-font theme locked

- The FF9 page theme is delivered as the shell `plugin.theme` config in
  `games/ff9/editor.js` (deep-navy menu surfaces, parchment-gold highlights,
  serif storybook headings) and applied by the shared framework `applyTheme`.
- Provenance boundary: CSS values plus system font stacks only. No proprietary
  FF9 font, image, or audio asset is bundled, downloaded, or referenced
  (recorded in `games/ff9/THIRD_PARTY.md` under "Theme provenance").
- Game-derived interface sounds are never shipped; they require local
  extraction from an installed copy when redistribution is not permitted.
- Locked by `tests/ff9_editor.test.cjs`: theme name/keys present, no
  `url()`/remote/binary asset reference, system font stacks asserted, exact
  navy (`#090d1a`) / panel (`#171f38`) / gold (`#d7c47a`) pins.
- `games/ff9/editor.css` stays at the shared-baseline budget (0 non-token rules).

Status: agent-side complete on `per-game-ff9`. Any remaining taste call is Lexer's.
