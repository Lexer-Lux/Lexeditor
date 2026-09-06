# GitHub #23 - Visible Gold Cores/Bars Overfill

## Requirement

Fortified player and horse cores and outer bars need a golden overlay whose
visible LENGTH is the remaining fortification, instead of the stock HUD's binary
gold state. Layout constraint: HUD scale 1.0 with the extended circular minimap.

## Four rejected attempts

1. Rectangle segments rotated tangentially into an arc. Returned: "why are they
   made of dots", "how are they all different sizes".
2. `rpg_textures` / `rpg_meter_N` drawn directly. Returned: "circles look better
   but they're covered with big yellow circles."
3. (same family, tuned) - still opaque discs.
4. Hand-authored `generic_textures` / `lex_fortification_meter_1..99`, 128x128
   DXT5 rings. Returned: not centred, "not nearly thick enough", "the default
   golden core still appears beneath it ... gold on gold".

Common cause of all four: the reference mod Lexer supplied was never actually
disassembled. It has now been.

## What the reference binary actually says

Static analysis of `_downloads/inspect/hardcore-stamina/Y_Hardcore_Stamina.asi`
(PE, 159232 bytes) with pefile + capstone. Reproduce with
`tools/reverse-engineering/verify_fortification_hud_issue_23.py`, which re-checks
every claim below against the raw bytes.

**Sprite helper at `0x1800026C0`** - one function, called for every element:

```
drawSprite(rcx = textureDict, rdx = textureName,
           xmm2 = left, xmm3 = top,
           [rsp+0xA0] = width, [rsp+0xA8] = height, [rsp+0xB0] = rotation,
           [rsp+0xB8/0xC0/0xC8/0xD0] = r, g, b, a)
```

It calls `HAS_STREAMED_TEXTURE_DICT_LOADED` (0x54D6900929CCF162); if the txd is
not loaded it calls `REQUEST_STREAMED_TEXTURE_DICT` (0xC1BA29DF5631B0F8) and
returns without drawing that frame; otherwise it adds `width*0.5` / `height*0.5`
to the supplied left/top (0.5f constant at RVA 0x1AC7C) and calls `DRAW_SPRITE`
(0xC9884ECADE94CB34). This is the identical request-then-draw rule that fixed our
custom map icons in `ensureLexBlipTextures()`.

**Draw sequence at `0x180008DFF`-`0x180009006`**, in order, with the tint each
one is given:

| # | txd | texture | tint |
|---|---|---|---|
| 1 | `rpg_textures` | `rpg_background` | 0,0,0,255 (dark core disc) |
| 2 | `rpg_meter_track` | `rpg_meter_track_9` | 0x6D,0x6D,0x6D (empty track) |
| 3 | `blips` | `blip_player_coach` | 255,255,255 (glyph in the disc) |
| 4 | `rpg_meter` | `rpg_meter_0` .. `rpg_meter_99` | 0xE5,0xE5,0xE5 (the fill) |

The smooth ring is **one authored Rockstar sprite per percent**, selected by
`sprintf`-ing `rpg_meter_%d` (format string at RVA 0x1AC38, bounds `rpg_meter_0`
at 0x1AC08 and `rpg_meter_99` at 0x1AC28, clamped by `cmp dword ptr [rax], 0x63`
at 0x180008FAD). No dots, no segments, no custom texture.

**The dictionary name was our bug.** The arc family lives in txd `rpg_meter`.
Attempt 2/3 drew `rpg_textures` / `rpg_meter_N`, which is a different resource -
that is what produced the opaque yellow discs. `GameplayTweaks/modules/recon.cpp`
records the same "white squares" symptom from the same mistaken dictionary; that
module is not owned by this issue but is very likely fixable the same way.

**Layout, `0x180008CE0`-`0x180008DBA`.** Everything is relative to one per-core
box (W, H) with top-left (X, Y). `xmm11` = 0.5f (0x1AC7C), and the two ratio
doubles are 0.9 (0x1ACC0) and 1.05 (0x1ACC8):

| element | quad | concentric |
|---|---|---|
| `rpg_background` (+ glyph) | 0.90 x (W, H) | yes |
| `rpg_meter_track_9` | 1.00 x (W, H) | - |
| `rpg_meter_N` | 1.05 x (W, H) | yes |

**INI encoding, parsed `0x180002E52`-`0x180002F19`.** `POSITION_X`/`POSITION_Y`
are multiplied by 1.0e-3 (constant at 0x1AC74); `WIDTH`/`HEIGHT` by 1.0e-4
(0x1AC70). So the shipped `[CORE_POSITION] WIDTH=242 HEIGHT=430` is a box of
0.0242 x 0.0430 normalised - a physical square on 16:9 - and that is the
author's own calibration of a vanilla core.

Its `POSITION_X=140 POSITION_Y=927` is deliberately **not** reused. That mod
paints one extra, user-placed core; its default position is evidence about the
author's preference, not about where Rockstar's five meters sit. Reusing it would
have put the overlay at normalised y 0.9485, which is inconsistent with the
minimap visible below the cores in Lexer's own screenshot.

## What the returned screenshots measure

The three images attached to the issue were downloaded and measured
(connected-component analysis, dark discs and gold pixels):

- Five vanilla core discs in the "dotted" screenshot sit on a fixed arc at crop
  centres (126, 223), (207, 190), (288.5, 176), (369.5, 190), (450.5, 223), disc
  diameter 57 px, step 81.3 px. The arrangement is stable between screenshots.
- In the attempt-4 screenshot our overlay ring for Health is centred at
  (81.0, 153.5) against a vanilla Health disc centred at (82.0, 153.5), and our
  Dead Eye ring at (244.0, 107.0) against a disc at (242.5, 107.0).

So **the seat table was not the defect** - it lands within 1-1.5 screenshot
pixels on both measured seats, and the seat table is kept unchanged. The real
defects were size (our ring outer diameter 73 px against a 57 px core disc, i.e.
riding outside the meter instead of on it) and the hand-drawn stroke
(10/128 of the texture inside a 118/128 circle - the "not nearly thick enough"
ring), plus the gold-on-gold layering.

## Implementation

`GameplayTweaks/modules/fortification_hud.cpp` was rewritten around the extracted
method.

- **(a) dots** - `drawSpentArc()` issues exactly one `GRAPHICS::DRAW_SPRITE` of
  `rpg_meter` / `rpg_meter_<0..99>`. No compositing loop, no custom dictionary,
  no authored texture. The verifier asserts the module contains exactly one
  `GRAPHICS::DRAW_SPRITE(` call site.
- **(b) alignment and thickness** - the quad is the reference's own calibrated
  box, 0.0242 x 0.0430, times its own 1.05 bar-ring ratio. The art is Rockstar's
  own ring, so its stroke is the vanilla stroke by construction. The seat table
  is unchanged because it measures correct. `[Fortification] NudgeX/NudgeY` and
  `BoxWidth/BoxHeight/BarRingScale/CoreRingScale` move and resize all five seats
  from the INI, exactly as the reference mod exposes the same four numbers, so
  any residual offset is a one-line edit rather than another build cycle.
- **(c) gold on gold** - the module now draws **nothing gold**. The game already
  paints the whole ring gold when the attribute is fortified, so a second gold
  arc can never read. Instead the SPENT fraction of the ring is repainted in the
  ordinary un-fortified meter colour (229,229,229 - the reference's own 0xE5
  fill colour, at 0x180008F31), leaving Rockstar's gold visible only for the
  fraction that remains. There is one gold layer because the mod never adds one,
  and the gold the player sees has vanilla colour, thickness and position.
  The core timer uses a concentric inner ring at 0.86 of the box whose spent part
  is repainted in the disc's own dark, so the fortified gold disc shows a clean
  shrinking arc instead of a flat gold circle.

Texture index is `round(spent * 99)`; `rpg_meter_0` is the empty frame, so a
fully-remaining effect draws nothing at all rather than wasting a draw call.

Independent bar and core timers are unchanged
(`_GET_ATTRIBUTE_OVERPOWER_SECONDS_LEFT` 0x4C9F782180712742 and
`_GET_ATTRIBUTE_CORE_OVERPOWER_SECONDS_LEFT` 0xB429F58803D285B1), as are the
peak-learning logic, the HUD/pause/cinematic suppression, and the mount seat
selection.

## Dead assets from attempt 4

`GameplayTweaks/icons/fortification/` (`prepare_fortification_meters.py`,
`build_fortification_generic_textures.ps1`, the 148-texture
`generic_textures.ytd`, SHA-256
`7FCD8B439915B08A32E3C4DA5E3A3361E179D454D462E11DE277B14055330571`) are no longer
referenced by this module. They are left in place rather than deleted because
`GameplayTweaks/modules/recon.cpp` still draws `lex_fortification_meter_N` from
that dictionary and recon is not owned by this issue. If a `generic_textures.ytd`
was copied into `MyOverhaul/stream/` for #23 alone, integration should decide
whether it is still wanted; nothing in #23 needs it now.

## Static verification

`python tools/reverse-engineering/verify_fortification_hud_issue_23.py` passes.
It re-derives every reference claim from the binary itself - the `rpg_meter`
dictionary and the `rpg_meter_0`/`rpg_meter_99` bounds as raw strings, the three
native ids as raw little-endian qwords, and the 1.05 / 0.90 ratios as raw IEEE
doubles - then asserts the module uses that method, contains exactly one sprite
call, adds no gold, repaints `1.0f - bar` and `1.0f - coreFill`, keeps the two
timers independent, and reads its `[Fortification]` section.

The module edits no dispatcher, no generated index, no install script and no
GitHub metadata, and uses only helpers already available before topic-module
includes (`GRAPHICS::`, `TXD::`, `HUD::`, `CAM::`, `invoke`, `GET_MOUNT`,
`g_iniPath`, `GetPrivateProfileIntA`, `<algorithm>`, `<cmath>`).

## Integration

1. Include `modules/fortification_hud.cpp` with the other topic modules in
   `GameplayTweaks/script.cpp`.
2. Call `updateVisibleGoldOverfill(ped, locked);` once per frame after `ped` and
   `locked` are calculated.
3. Ship the new `[Fortification]` section already appended to
   `GameplayTweaks/GameplayTweaks.ini`.

## Honest open points for the in-game test

- `rpg_meter` is proven to be the dictionary the reference mod streams and draws
  from, but the exact pixel geometry of `rpg_meter_N` inside its quad cannot be
  read statically - that would need the txd itself. If the arc lands slightly
  large or small, `BarRingScale` / `CoreRingScale` / `BoxWidth` / `BoxHeight`
  correct it from the INI without a rebuild.
- The arc's fill direction and start angle are Rockstar's. If the surviving gold
  ends up anchored at the wrong end of the sweep, that is a texture-index
  inversion, not a geometry problem.
- The outer bar and the core use the same ring family at two radii. Only
  `rpg_meter_track_9` is proven to exist in `rpg_meter_track`; no fractional
  track family was found in the binary, so the core timer deliberately uses the
  proven `rpg_meter` art at a smaller radius rather than guessing at
  `rpg_meter_track_<N>`.

## Current actionable pass

The development build now has a live five-meter layout calibrator. Numpad 0
claims/releases the controls, Numpad 1 cycles Health/Stamina/Dead Eye/player-
horse Health/player-horse Stamina, 4/6 and 8/2 move the selected meter, 7/9
changes scale, Shift selects fine steps, and 5 persists the per-seat values.
Full rings are previewed during calibration even without a tonic. Camera
calibration yields the same numpad while this tool owns it. Static verification
passes; visual acceptance remains in game.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-10 returned calibrator repair

Lexer reported that Numpad 0 did nothing. The controls were present in source,
but `updateCalibration()` was still gated by `developmentModeActive()`. Later
normal builds therefore made the explicitly requested layout tool unreachable.
The fortification calibrator is now called in normal builds; it remains dormant
until Numpad 0 toggles it and continues to own the shared numpad while active.
Unrelated developer controls remain compile-time gated. Static verification now
rejects any restored development-mode gate around this calibrator.

## 2026-08-10 returned overlay correction

The installed test showed three remaining defects. Calibration composited its
selected inner ring and the live fortification pass under its outer preview,
visibly producing two rings. The runtime renderer depended on Rockstar's
binary fortified tint for the gold that remained, so stamina could follow the
same timer while never appearing gold. Finally, repainting only the spent
fraction made a white arc visibly grow while the intended gold arc shrank.

Calibration now draws exactly one outer preview ring per seat and suppresses
the live overlay while active. Runtime meters first place a static authored
normal/dark mask over the vanilla binary tint, then draw the measured remaining
fraction explicitly in gold at identical geometry. The neutral layer therefore
does not grow, the visible gold length shrinks directly, and stamina no longer
depends on its vanilla tint state. The gold RGBA is exposed in the INI. Static
verification covers the mutually exclusive calibration and explicit two-layer
meter contract; combined build/install and in-game confirmation remain pending.

Combined release build succeeded with queued ASI SHA-256
`1EF0C29A5DD946673827ECDDEA1B5C6800BD148B5F2E3111256A5446CBA2707A`.
RDR2 was running, so installation remained pending.

Rebuilt with the #5/#128 integration as ASI SHA-256
`AEAE1D1D1C53861A6F507815030957D333E77D097E9F2E7F899EF5B2FF82B2A3`;
installation remained pending while RDR2 was running.
## fuckups.txt recurrence audit

- Texture presence, archive construction, and a successful draw call are not proof that the player sees the requested fortification HUD.
- Any release candidate must preserve the authored asset, prove the module reaches the draw path, and leave actual placement, legibility, and obstruction as explicit in-game acceptance.

## 2026-08-10 returned double-ring root cause

The latest screenshot/result was not a mysterious duplicate draw. The module
explicitly rendered two concentric authored rings for every meter whenever both
timers were active: one at `BarRingScale` and a second at `CoreRingScale`. The
source comment even described the smaller ring as the core-timer presentation.
That was an invented presentation choice which directly contradicted Lexer's
repeated requirement that one meter show one visible circular overlay.

The repair removes the inner/core ring draw path. Each seat now has exactly one
outer authored ring. Its displayed fraction is the greater of the enabled bar
and core remaining fractions, so core-only fortification remains visible and a
simultaneous core+bar boost cannot create a second circle. The full neutral mask
and shrinking gold fraction share the exact same geometry. Static call counts
must reject any return to separate bar/core ring geometry; visual acceptance
still requires one and only one circle per meter in game.
