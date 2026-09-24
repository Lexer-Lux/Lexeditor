# Original CRT presets on DirectX 11

This add-on runs the user's original PS1 and N64 RetroArch shader chains with
librashader. It does not translate a small subset of matching parameter names.
This is a local FF7 Remake Part 1 candidate, not the shared mod installer.

Start the game with its existing DX11 setting. PS1 is selected at startup.
Press **Home** to open ReShade. Select `Lexer-PS1.ini` or `Lexer-N64.ini` at the
top. **Scroll Lock** or the **Lexer CRT** checkbox toggles the effect.
The first selection compiles the full 30-pass chain and can pause briefly.

Both original presets are included. A wrapper disables the Mega Bezel startup
intro so it does not hide the game during startup. All other preset values and
shader files remain intact. Input is the game's current-resolution frame, not
an emulated console framebuffer. The input and output resolution affect the
result. N64 keeps its saved 4:3 layout, cropping and border. PS1 keeps its saved
full-width layout.

Both chains have rendered on a real DX11 device in an offscreen test. The test
also checks immediate-context state restoration. This does not establish
FF7 Remake in-game acceptance.

Errors appear in the ReShade Log tab and `ReShade.log`. If an effect is missing,
check the Add-ons tab for Lexer CRT and check the selected preset and checkbox.
An error disables that preset until the user switches presets or restarts.

## Changing the settings

Open ReShade (Home) and go to the **Lexer CRT** tab. It lists every setting of
the running chain in the chain's own order, under Mega Bezel's section titles,
as sliders limited to each setting's range and step. Changes apply on the next
frame. **Save** writes the settings that differ from the original chain into
`LexerCRT/PS1.slangp` or `N64.slangp`, beside the game, as RetroArch-style
overrides on top of `#reference "PS1-original.slangp"`; RetroArch reads the
same file. **Revert** returns to the last save and **Original** to the original
chain. A `*` marks a setting that differs from the original chain; hover a
slider for its parameter name and original value. The filter box searches
labels and names.

## Implementation

The renderer records on its own deferred context and submits with
`ExecuteCommandList(..., TRUE)` to restore the game's immediate-context state.
It copies the input before drawing to the output to avoid read/write aliasing.
It recreates the input resource after resize and clears history on that frame.
The add-on only runs for the two named presets and an enabled Lexer CRT effect.

Build with `source/build.cmd <sdk> <out>` (MSVC 2022 Build Tools, x64, C++17,
`/LD /O2 /MT`). The SDK folder holds the ReShade 6.8 add-on headers, Dear ImGui's
`imgui.h`/`imconfig.h` at ReShade 6.8's commit `3912b3d9` (1.92.5 docking; the
overlay refuses any other version) and librashader 0.12 headers. Link `d3d11.lib` and `librashader.dll.lib`. Name the
output `LexerCRT.addon64`. The import library expects `librashader_capi.dll`;
use that name for the supplied `librashader.dll` binary. Dependencies must be
available in the game executable directory or the Windows runtime installation.
`package_local.py` prepares the preset selector and files in a supplied local
build directory. It does not install into a game or overwrite existing mods.

## Sources and credits

- [ReShade](https://github.com/crosire/reshade), 6.8.0 full add-on build, Patrick Mours.
- [librashader](https://github.com/SnowflakePowered/librashader), 0.12.0, chyyran.
- [Mega Bezel](https://github.com/HyperspaceMadness/Mega_Bezel), HyperspaceMadness
  and the authors named in its shader source, including guest(r) and dogway.
- The user's Steam Deck supplied the original presets and their exact shader files.

This directory stores source, presets and the shader chains. Built and
downloaded runtimes (`LexerCRT.addon64`, `librashader_capi.dll`, ReShade's
`dxgi.dll`) are not tracked; the last build lives in
`%LOCALAPPDATA%/Lexeditor/reshade/crt-build`. Preserve the licenses in all
shipped source.
