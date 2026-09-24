# Shaders

- `reshade/`: Lexeditor's own ReShade effects. The app deploys this folder into
  each game's ReShade install and shows every effect's sliders on its Tweaks page.
- `crt/`: the PS1 and N64 CRT looks. They are 30-pass RetroArch chains run inside
  ReShade by the Lexer CRT add-on, so they live apart and are never deployed with
  the effects above. See `crt/README.md`.

## Selection

### Selected
- Color grading (colors, contrast, exposure and black levels)
- Sharpening
- Debanding
- SMAA
- Bloom
- Ambient occlusion
- Depth of field (optional per game)
- Film grain (optional per game)
- Vignette (optional per game)
- PS1 and N64 original CRT presets (`crt/`)

### Utility effects
- Before/after split view
- Depth-buffer viewer

### Candidates, not yet selected
- Ambient light and local contrast
- Light rays
- Screen-space reflections
- Screen-space indirect lighting
- Motion blur
- Lens dirt, lens flares and chromatic aberration
- Cel shading, outlines, watercolor and other stylized looks
- Dithering and restricted color palettes
- Image overlays and letterboxing

Per-game presets choose settings and enabled effects from a shared collection.
Depth effects need a usable game depth buffer and per-game testing.
This records effect categories. Individual shader implementations and redistribution terms still need review.
