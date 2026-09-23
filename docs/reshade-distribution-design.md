# Shipping ReShade presets with a Lexeditor mod

Lexer's requirement: add ReShade presets with mods, keep one ReShade managed by
Lexeditor rather than a copy per mod, and have a published mod still work for
someone who does not use Lexeditor.

## What Lexeditor owns

- **ReShade itself**, pinned (6.8.0, add-on build) and bundled in
  `tools/reshade/`. It installs per game under the loader name the game's
  renderer needs, into the folder the plugin declares (`reshade_root`), in the
  32-bit or 64-bit build matching the executable Play starts. A file of that
  name that is not ReShade is never overwritten or removed.
- **ReshadeEffectShaderToggler**, pinned and bundled in `tools/reshade/addons/`,
  installed beside ReShade so effects can run before a game draws its HUD.
- **The effects**, Lexeditor's own, in `shaders`: Colors,
  Bloom, Sharpen (AMD CAS), AmbientOcclusion, DepthOfField, Vignette and Compare,
  with one shared depth setup in `LexerianDepth.fxh`. They are always on
  ReShade's search path. No third-party shader collection is downloaded.

## What a mod owns

A project's `reshade/` folder:

- a preset `.ini`, the creative content;
- `shaders/`, any shaders the author wrote;
- `reshade.json`: whether the preset is on, which preset, and the renderer.

## What a player who does not use Lexeditor gets

The preset is a plain ReShade preset. Writing the by-hand install note
(`INSTALL-RESHADE.txt`) also copies Lexeditor's effects into the mod's
`reshade/shaders/Lexerian`, since they are Lexeditor's own work and may travel
with it. The note names the loader DLL, says to copy the shaders folder and
where the preset goes, and opens by saying the reader does not need Lexeditor.
