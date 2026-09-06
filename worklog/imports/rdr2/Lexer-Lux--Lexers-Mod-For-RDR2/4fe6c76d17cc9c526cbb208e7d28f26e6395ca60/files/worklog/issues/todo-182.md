# Worklog: Todo 182

## #182 recon tags rebuilt on Rockstar's core language — 2026-08-04

Build `955A9E6CE8777634504C32BDFF7ACA76CAD72A6F28E7EAF55E4CA64CAA4C5B3F`.

The inner marks were `drawReconText` characters — "!", "*", "+", "." — which
read as debug output rather than a game UI element. Replaced with real sprites
from the `MINIMAP_BLIPS` dictionary, which is already streamed every frame by
`reconEnsureBlipTextures()` for the owned-horse glyph, so there is no extra cost.

Sprite names taken from the 321 extracted vanilla blip textures in
`GameplayTweaks/icons/vanilla/png/blips/` — these ARE the texture names in the
dictionary, which is how `blip_horse_owned` was known to work:
  Enemy    -> blip_ambient_bounty_target
  Animal   -> blip_animal
  Ally     -> blip_ambient_companion
  Neutral  -> blip_ambient_npc
  Horse    -> blip_horse_owned  (unchanged)
Outer seat ring -> `blip_overlay_ring`, drawn dark (24,24,24,210) at 2.35x radius
underneath the health arcs so the marker reads as a core rather than a floating
arc. Health arcs and the metre distance are unchanged.

If the dictionary has not streamed, the inner sprite draws NOTHING. Deliberate:
the previous "H" text fallback became permanent and was reported as a bug.

