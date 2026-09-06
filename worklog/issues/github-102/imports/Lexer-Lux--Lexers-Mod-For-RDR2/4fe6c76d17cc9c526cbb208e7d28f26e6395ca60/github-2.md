# GitHub #2 — Recon Tag Appearance Rework

## Requested appearance

Each overhead recon tag must read like a vanilla Rockstar core: the selected
identity icon in the center and one radial bar around it showing that target's
live HP. It must not substitute text glyphs or show arbitrary extra-health
color layers.

## Evidence and implementation

The installed Hardcore Stamina reference at
`_downloads/inspect/hardcore-stamina/Y_Hardcore_Stamina.asi` contains the exact
resident Rockstar sprite stack `rpg_textures`, `rpg_meter_track_9`,
`rpg_meter_track`, and `rpg_meter_0` through `rpg_meter_99`. The existing wagon
Stamina feature had already proven the corresponding draw order and neutral
palette. The two linked native-UI repositories independently support using
Rockstar's resident sprites and aspect-correct screen coordinates; no code or
assets were copied from them.

`drawReconMarker` now uses that genuine core stack. It chooses
`rpg_meter_N` from `GET_ENTITY_HEALTH / GET_ENTITY_MAX_HEALTH`, draws the black
backing and gray track, draws the tag's selected vanilla blip in the center,
then draws the off-white live HP fill. Enemy, animal, ally, neutral, and owned
horse retain their distinct chosen icons. The previous hand-built 36-rectangle
ring and red/yellow/blue `HealthPerLayer` scheme no longer participate in ped
tags; plant/object markers remain outside this issue because they have no HP.

## Static verification and integration

`python tools/reverse-engineering/verify_recon_appearance_issue_2.py` verifies
the local reference strings, actual-health fraction, Rockstar meter stack and
draw order, all five center-icon paths, and absence of the legacy layered HP
logic in `drawReconMarker`.

The existing dispatcher already includes `modules/recon.cpp`, requests tag
textures every frame, and calls `updateReconTagging`; no `script.cpp` change is
needed. The integration owner should build/install normally and may remove the
now-obsolete `ReconTagging/HealthPerLayer` INI setting in a shared-file cleanup.

## Runtime acceptance boundary

Static inspection cannot prove sprite scale, alpha, or draw ordering in the
actual HUD. After install, tag at least an enemy, animal, ally/neutral, and the
owned horse. Each must show its selected icon centered inside a smooth
Rockstar-style core, with one radial ring that falls continuously as real HP
falls. Check multiple simultaneous tags, 16:9 and the user's normal resolution,
pause/satchel suppression, and that plant tags remain intact. No build, install,
game control, GitHub mutation, commit, or push was performed here.

## 2026-08-06 returned-test correction: opaque HUD masks removed

Two installed tests showed every recon core as a white square. The same failure
was independently reproduced by the wagon meter and fortified-core overlays:
`rpg_meter_N`, `rpg_meter_track`, and `rpg_meter_track_9` are HUD masks, not
transparent textures suitable for direct `DRAW_SPRITE` use. Drawing them this
way colors their opaque rectangle.

Recon now uses the complete resident `GENERIC_TEXTURES` replacement's
alpha-backed `lex_fortification_meter_1..99` rings. A subdued full ring supplies
the track, the selected identity icon remains in its transparent center, and the
live-health ring is drawn only above zero. All direct `rpg_meter`/track draws
were removed from `drawReconMarker`. The revised #2 verifier rejects those
opaque masks and passes. This is local/static evidence only; #2 remains
`actionable` until the combined build and merged texture archive are installed.

## 2026-08-06 (second pass) — the "opaque HUD mask" theory was itself wrong

The previous entry above concluded that `rpg_meter_N`, `rpg_meter_track` and
`rpg_meter_track_9` are opaque HUD masks and replaced them with a custom
`generic_textures` / `lex_fortification_meter_N` family. That conclusion does
not survive `fuckups.txt` entry 12, which was written after someone actually
disassembled the reference mod Lexer supplied
(`_downloads/inspect/hardcore-stamina/Y_Hardcore_Stamina.asi`): the reason those
draws came out opaque was that they were issued against the WRONG DICTIONARY —
`rpg_textures` instead of `rpg_meter`. The reference mod draws exactly these
textures and produces vanilla-looking cores, so "they are masks" is disproven by
a shipped binary that does it successfully.

The replacement was also unverifiable by construction:
`MyOverhaul/stream/generic_textures.ytd` is RSC8-compressed, so no name inside
it can be confirmed statically. Shipping a HUD that depends on unreadable custom
art is the same bet that produced #23's four failed builds.

### Changed in `GameplayTweaks/modules/recon.cpp`

- `drawReconMarker()` now draws Rockstar's own authored core art, in the
  reference mod's own order and concentric scales (recorded in
  `modules/fortification_hud.cpp:26-47`):
  `rpg_textures/rpg_background` at 0.90, `rpg_meter_track/rpg_meter_track_9` at
  1.00, the tag glyph, then `rpg_meter/rpg_meter_<percent>` at 1.05, drawn last
  because its centre is transparent. `rpg_background` is Lexer's missing
  "black circle background the cores have".
- All `generic_textures` / `lex_fortification_meter_*` use is gone from this
  module.
- Each backing layer is gated on its OWN dictionary being loaded and its own INI
  switch (`[ReconTagging] CoreBackground`, `CoreTrack`), so one bad layer cannot
  blank the whole tag and can be answered by an INI edit rather than a rebuild.
- `reconEnsureBlipTextures()` requests `blips`, `rpg_textures`,
  `rpg_meter_track`, `rpg_meter` and `lex_blips` every frame
  (`HAS_STREAMED_TEXTURE_DICT_LOADED` 0x54D6900929CCF162 /
  `REQUEST_STREAMED_TEXTURE_DICT` 0xC1BA29DF5631B0F8, the same pair used at
  `fortification_hud.cpp:336-337` and `collectibles_map.cpp:822-823`).

### Sprite names, and which file is actually the authority

`fuckups.txt` entry 17 lists four sprite names in this function as "CONFIRMED
ABSENT". That check was made against `MyOverhaul/blipdata.ymt`, which is the
wrong file for the question. `blipdata.ymt` `<Linkage>` values are blip STYLE
linkage ids; they are not a manifest of any texture dictionary's contents.

The authority for a `DRAW_SPRITE` texture name is the dictionary itself, and
this repo has the resident `blips` dictionary unpacked sprite-by-sprite at
`GameplayTweaks/icons/vanilla/png/blips/` — 321 files, described in
`GameplayTweaks/icons/README.md` as the full extraction used to rebuild the
dictionary in `build_blips_override.ps1`. Checked against that extraction:

| sprite drawn | file |
| --- | --- |
| `blip_overlay_ring` | `vanilla/png/blips/blip_overlay_ring.png` |
| `blip_plant` | `vanilla/png/blips/blip_plant.png` |
| `blip_horse_owned` | `vanilla/png/blips/blip_horse_owned.png` |
| `blip_ambient_bounty_target` | `vanilla/png/blips/blip_ambient_bounty_target.png` |
| `blip_animal` | `vanilla/png/blips/blip_animal.png` |
| `blip_ambient_companion` | `vanilla/png/blips/blip_ambient_companion.png` |
| `blip_ambient_npc` | `vanilla/png/blips/blip_ambient_npc.png` |

All seven are present. The one name known to have failed in game,
`blip_ambient_herb` (#96's white square), is absent from the same directory — so
the extraction reproduces both the known failure and the known successes, which
is what makes it usable as evidence. Names are now written in the extraction's
own lower case throughout, instead of being switched to `blipdata.ymt`'s
upper-case linkage spelling. No sprite was removed or substituted on the basis
of the blipdata.ymt check.

### Distance-text font

Lexer: "the font on the distance text is still wrong. Should be the RDR lino
font". Root cause of every previous failure to change it: **there is no
font-selection native**. Grepping `FONT` across both native header dumps on disk
(`_downloads/RDR2_SDK/SDK/inc/natives.h`,
`_downloads/NativeMenuBase/RDR2-Native-Menu-Base-master/inc/natives.h`) returns
only `NEXT_ONSCREEN_KEYBOARD_RESULT_WILL_DISPLAY_USING_THESE_FONTS`, which is
unrelated. The face is selected by markup inside the literal string, as
Halen84's RDR2-Native-Menu-Base — one of the two references Lexer linked on this
issue — does at `src/NativeMenuBase/UI/Drawing.cpp:275`, feeding the result
through the same `_CREATE_VAR_STRING(10, "LITERAL_STRING", …)` + `_DISPLAY_TEXT`
pair this module already used (`Drawing.cpp:281`).

`drawReconText()` now emits `<FONT FACE='$…'>…</FONT>`.

Honest limit: **no face named "lino" exists.** It is not in that project's
enumerated face list (`Drawing.cpp:112-113`: `body`, `body1`, `catalog1`..
`catalog5`, `chalk`, `Debug_BOLD`, `FixedWidthNumbers`, `Font5`, `gamername`,
`handwritten`, `ledger`, `RockstarTAG`, `SOCIAL_CLUB_COND_BOLD`, `title`,
`wantedPostersGeneric`), and a case-insensitive grep for `lino` across
`_downloads/RDR2-Decompiled-Scripts` returns only the horse breed `PERLINO`
(`script_rel/utopia1.c`). Rather than invent a name, the face is
`[ReconTagging] DistanceFont`, defaulting to `body`. The exact face can now be
settled by editing one INI line instead of by another rebuild.

### Not done here

No build, install, commit, push or label change. `tools/reverse-engineering/
verify_recon_appearance_issue_2.py` still encodes the disproven "rpg_meter is an
opaque mask" rule and will now fail; it is not an owned file of this pass and
needs updating by whoever owns it. It is not wired into `GameplayTweaks/
build.bat`, so it does not block a build.

## 2026-08-09 returned-test correction: literal markup and white core

The last in-game screenshot proved two concrete defects remained:

- The distance label displayed the literal `<FONT ...>` tag. The supplied
  NativeMenu reference never sends a bare FONT tag. Its
  `Drawing.cpp:253-283` uses a complete `TEXTFORMAT/P/FONT` wrapper, prefixes the
  payload with `~s~`, and transforms centred x from 0..1 to -1..1. Recon now
  follows that exact path. The same reference's `inc/enums.h:3-21` identifies
  `title` as **RDR Lino**, disproving the earlier claim that no Lino face was
  available; `DistanceFont` now defaults to `title`.
- The background was tinted white. The already-recorded disassembly of Lexer's
  Hardcore Stamina reference in `worklog/issues/github-23.md` gives the exact
  tints: `rpg_background` = `0,0,0,255`, `rpg_meter_track_9` =
  `109,109,109,255`, and `rpg_meter_N` = `229,229,229,255`. Recon now uses those
  exact values instead of white/white/off-white.

`verify_recon_appearance_issue_2.py` was corrected to reject the obsolete
custom-ring theory and now verifies the actual reference dictionaries, tints,
full text wrapper, RDR Lino default, live HP fraction and all five center-icon
paths. It passes. These source changes have not been built or installed yet so
the separately installed crash-fix candidate remains unchanged for its runtime
test. #2 stays `actionable`.

## Installed handoff

The corrected appearance shipped in development ASI
`BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5`;
source and game-root hashes match. #2 was manually changed from `actionable` to
`test me` and read back as open with `high priority,test me`. Runtime acceptance
is the black core background, grey track, live white HP arc, correct center icon,
and literal RDR Lino distance text on both human and animal tags.

## Current actionable pass

The next appearance correction removed the world-space Z nudge that made tag
height vary with distance. The tag now derives a screen-space pixel gap from the
projected head anchor. Distance text and its shadow are separately configurable.
Acquisition uses a keyless, nonlinear opacity ramp and no longer draws the
misleading `Studying` label or dotted progress ring; the completed tag becomes
fully opaque only when acquisition finishes. The issue verifier passes. This
attempt is source-only until the combined release is installed.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-10 actionable correction: capacity layers and horse-core source

Lexer's returned test established three concrete remaining defects: distance
text overlapped the core, the grizzly's health was collapsed into one normalized
ring, and the owned horse showed a full ring while its visible health core was
about one quarter.

`drawReconMarker()` now uses one concentric authored `rpg_meter` ring per 100
health. Each ring draws the maximum capacity in grey and current health in white;
the remainder is left transparent, giving the requested white / grey / clear
states. A 261-HP animal therefore has three overlapping capacity rings rather
than one full bar. The owned horse reads the same health core native used by the
player HUD (`GET_CORE(horse, 0)`) instead of unrelated entity HP. The default
`DistanceTextGapPixels` increased from 3 to 14 and remains hot-reloadable.

`verify_recon_appearance_issue_2.py` verifies the fixed 100-HP layers, both
tints, transparent unavailable capacity, horse-core readback, and new distance
gap. It passes. This is build evidence only; #2 remains `actionable` until the
combined artifact is installed and hash-verified.

## 2026-08-10 returned-test repair: plants, horse capacity, binocular height

The latest three in-game screenshots isolated three different defects in the
same marker renderer:

- Plants still called the legacy `blip_overlay_ring` + `drawReconArc` +
  `drawReconDisc` object path, so they visibly retained the retired hand-built
  appearance. `drawReconObjectMarker()` now uses the same verified
  `rpg_background` black disc and authored `rpg_meter_99` white ring as the new
  tags, with `blip_plant` retained in the centre.
- The owned-horse branch treated `GET_CORE(horse, 0)` as current health and a
  hard-coded 100 as fillable capacity. A fully healed horse whose health stat
  capacity was 85 therefore rendered 85 white / 15 grey even though that final
  15 was not fillable. Rockstar's `player_horse.c:18650-18666` maps horse stat
  0 (health) to attribute 16, and `player_horse.c:11805-11821` reads that stat
  with `GET_ATTRIBUTE_BASE_RANK`. Recon now uses attribute 16 as the 0..100
  fillable capacity and scales entity HP (excluding Rockstar's 100-point living
  ped floor) into it. Full 85-capacity health is 85 white / 15 clear; damage
  turns only the fillable part grey.
- `SKEL_HEAD` is near the skull centre. The configured pixel gap was measured
  from that bone, so binocular magnification enlarged the visible distance from
  the bone to the crown until the tag overlapped the head. The screen anchor now
  projects the four top corners of cached model bounds, keeps the head X, and
  uses the highest visible Y before applying the same pixel gap.

`python tools/reverse-engineering/verify_recon_appearance_issue_2.py` passed. It
now rejects the legacy plant draw, proves the authored plant stack and projected
silhouette-top anchor, verifies the horse attribute-16 mapping against
Rockstar's decompiled script, and rejects the incorrect horse `GET_CORE/100`
path. This pass was source/static only; no build, install, game launch, shared
dispatcher/INI/manifest edit, or GitHub mutation was performed.

## 2026-08-10 recurrence audit before the latest repair

- **Primary evidence/reference:** the newest live report says a grizzly renders
  two concentric health rings. The requested appearance is one vanilla-style
  core whose single radial capacity is white current, grey lost-but-fillable,
  and transparent unfillable capacity. The Hardcore Stamina disassembly and
  extracted `rpg_meter` dictionary remain the only sanctioned texture source;
  the current renderer and installed log must establish why it emitted two
  rings before any further change.
- **Sanctioned path:** use one authored Rockstar `rpg_meter_N` ring around one
  black `rpg_background`, with live ped health and proven maximum/fillable
  capacity. Do not synthesize dotted arcs, duplicate rings per 100 HP, or infer
  animal capacity from species folklore.
- **Execution proof:** diagnostics must record the target, resolved current and
  maximum health, selected ring percentage, and number of rings actually drawn.
  A draw-call log is not visual acceptance.
- **Player-visible acceptance:** a grizzly and ordinary human each show exactly
  one core ring; damage changes only its white/grey/clear proportions; the
  owned horse does not claim a tiny sliver when its real health is healthy.
- **Every per-frame native:** projection, health, and draw natives are permitted
  only for a currently visible recon target. Model bounds and maximum capacity
  must remain cached/bounded. No new global per-frame scan or setter is allowed.

## 2026-08-10 returned-test root cause and repair

The grizzly's concentric rings were not an engine artifact or an accidental
duplicate draw. The previous implementation explicitly calculated
`ringCount = ceil(maxHealth / 100)` and looped over those layers with an added
`0.13` scale per layer. That implemented an earlier request literally, but the
newest live report rejects that presentation and the current requested
appearance is one vanilla-style core.

The renderer now performs exactly one grey capacity draw and one white current
draw at one scale. Ordinary peds/animals normalize current entity health into a
single 0..99 authored `rpg_meter` frame. The owned horse uses attribute 16 as
its fillable capacity and `GET_CORE(horse, 0)` as the current health-core
readback; the entity-health-floor scaling that produced the reported tiny false
sliver is gone. The undrawn remainder beyond horse capacity remains clear.

A bounded two-second diagnostic records target, horse flag, entity HP,
health-core readback, capacity frame, current frame, and `rings=1`. This is
execution evidence, not visual acceptance. `python tools/reverse-engineering/
verify_recon_appearance_issue_2.py` statically rejects the old loop/floor path
and verifies the single authored core. Runtime acceptance remains: one ring on
a grizzly and human, and an owned-horse core consistent with the visible vanilla
horse core through healthy and damaged states. No build/install/shared file or
GitHub state was changed.
