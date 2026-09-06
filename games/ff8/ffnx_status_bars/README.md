# FF8 XP, HP and GF HP bars

This directory contains an isolated FFNx source extension. It does not patch
`FF8_EN.exe` and it does not use Hext. Apply it only to FFNx revision
`1e291885da4ddb482188b81a5198d56a1915fde6`:

```text
python games/ff8/ffnx_status_bars/apply_to_ffnx.py <FFNx source directory>
```

The derivative build adds three default-off FFNx settings:

- `enable_ff8_xp_bars`: level-progress bars on the main menu, Status screen,
  and post-battle report.
- `enable_ff8_hp_bars`: current/max HP bars for the three active characters in
  battle.
- `enable_ff8_gf_hp_bars`: blue, left-to-right HP bars above party names.
  Multiple junctioned GFs contribute combined current/max HP.

Lexeditor stores the choices as `xpBars`, `hpBars` and `gfHpBars` in each mod's
`lexeditor-settings.json`. At the launch barrier, it writes the selected mod's
values to the derivative settings in the active `FFNx.toml`. Changing mods
therefore does not share these choices with another mod.

## Primary evidence

The supported executable is the Steam English `FF8_EN.exe` with SHA-256
`064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`.
Official FFNx resolves the menu callback table, savemap, character-level
function, battle character IDs, and the three computed battle-stat records for
this executable.

The native Status renderer at `004CECF0` reads the selected character at state
offset `0x36` (`004CEF94`) and forms that character's savemap address at
`004CEFA5`. The main-menu renderer is callback 16's pushed renderer
`004E5550`. The post-battle dispatch call at `004A3E59` invokes renderer
`004A4950`. Its controller calls the native XP updater at `004A4461`, writes
the displayed running XP total at `004A4485`, and advances that total at
`004A48B1`. The extension observes those renderers and reads existing native
state. It uses FF8's own `get_char_level_4961D0` function to find exact level
boundaries instead of duplicating the XP formula.

FFNx exposes exactly three `ff8_char_computed_stats` battle records. The
verified layout stores current HP at offset 370 and maximum HP at offset 372.
The HP overlay captures the visible native HUD row instead of duplicating
its display-state calculation. The red line is at row Y + 14, the final pixel
of the native 15-pixel row; the blue GF line is at Y + 1, immediately above
the name at Y + 2. Glyph atlas padding is not used for vertical placement.

GF HP comes from junctioned, existing saved GFs and the native computed GF
maximum-HP table. While summoning, the active GF's live current/max HP in the
summoner's computed record takes precedence over saved values. This reflects
incoming damage before the game writes it back to the save-state copy.

## Integration points

The applicator copies the module under `src/`, adds the three TOML settings, and
adds these calls:

- `lexeditor_ff8_bars_install()` in `ff8_init_hooks()`.
- `lexeditor_ff8_bars_draw()` after `ImGui::NewFrame()`.
- `lexeditor_ff8_bars_enabled()` to all three renderer overlay lifecycle gates.

## Acceptance boundary

The verifier proves the supported executable bytes, official FFNx symbols,
default-off settings, hook locations, and state-selection rules. A live game
test is still required to confirm the final bar positions, scale, colors,
animation, and absence of flicker on every supported screen. This work does not
launch or install the game.

## Current derivative build

The packaged issue-51 derivative uses FFNx `c056db2783f376a340fcefa6a48cc33618998876`.
For that combined derivative, use `tools/prepare_ff8_native_build.py` on a
clean checkout rather than the older standalone applicator above. The script
replays the package provenance patch and copies these canonical sources.
It does not install a driver. A new binary must be built, verified and
packaged before source edits affect the running game.
