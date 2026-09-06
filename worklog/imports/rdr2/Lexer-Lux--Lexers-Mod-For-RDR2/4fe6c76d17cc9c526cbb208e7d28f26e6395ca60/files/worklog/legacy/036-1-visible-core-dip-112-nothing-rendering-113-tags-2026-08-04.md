# Worklog: 036 1 Visible Core Dip 112 Nothing Rendering 113 Tags 2026 08 04

## #1 visible core dip, #112 nothing rendering, #113 tags — 2026-08-04

Build `4B3341C3C650220BB1E64650131C022EB8379D8B031270EFA0E03A7CA6AA02DA`,
installed and hash-verified, INI synced. Full restart required.

- #1 visible dip. Sprint cut was hardcoded at `staminaBar <= 0.6f`, close enough
  to empty that the engine still got frames to spend the core, and the core pin
  lived INSIDE the `staminaEmpty` branch and only reacted to a decrement it had
  already observed — guaranteeing at least one rendered dip-then-restore frame.
  Now `[NoReserveCores] SprintCutBarPercent` (default 3.0, hot-reloads) drives
  the cut, recovery hysteresis is cut+1.5, and the core is pinned whenever the
  bar is under 2x the cut threshold, before any spend.
- #112. `Mode=engine_tracer` makes `updateProjectileVisibility` return
  immediately (`if (g_projectileVisibilityMode != 2) { clear; return; }`), so the
  ASI drew nothing at all. The CWeaponInfo tracer write is a data change needing
  the build step plus restart and was never proven to render. Net effect: Lexer
  had ZERO bullet visibility. Default reverted to `corona`. engine_tracer must be
  demonstrated to actually draw before it is defaulted again.
- #113 tag overlap. `reconAnchor` used head bone 21030 with only +0.18 m, putting
  the marker on the head. Now +0.52 m.
- #113 "H" glyph. `drawReconMarker` requested `MINIMAP_BLIPS` and tested
  `HAS_STREAMED_TEXTURE_DICT_LOADED` in the same call, which cannot succeed on
  first use, so the `drawReconText("H")` fallback became permanent. Added
  `reconEnsureBlipTextures()`, called every frame from `updateReconTagging`, and
  removed the letter fallback entirely — draw nothing until the sprite streams.

INI note: `[NoReserveCores]` appeared TWICE in GameplayTweaks.ini. GetPrivateProfile*
reads the first section only, so a setting added to the second copy is silently
ignored. The new key went into the first section; do not re-add the duplicate.

