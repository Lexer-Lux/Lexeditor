# FF8 editability: what Lexeditor changes, and what the other tools do

Answers the standing question "is everything editable that should be, and does
this cover what the older FF8 editors cover". Every claim below is either read
out of this repository or taken from a named tool's own documentation; the
survey date is 2026-09-25. Sources are credited in `ui/credits-sources.json`
under the `ff8` plugin.

## What the plugin edits

The Data Map is the plugin's own statement of coverage (`data_map_rows()` in
`plugins/ff8/formats.py`), and the tables below repeat it:

| Area | File | State |
| --- | --- | --- |
| Characters, Magic, GFs, weapons, battle items, commands, abilities, linked names | `kernel.bin` | partial: every named field and all linked text |
| Item prices and sell multipliers | `menu/price.bin` | all fields |
| Shop inventories and rare-stock flags | `menu/shop.bin` | all fields |
| Weapon upgrade prices and ingredients | `menu/mwepon.bin` | all fields |
| Menu item types, use flags, parameters | `menu/mitem.bin` | every meaningful field |
| Starting party, inventory, GFs, junction, config | `init.out` | named starting fields |
| Tutorial text, all 377 refine and card-mod recipes | `menu/mngrp.bin` | partial: text and recipes |
| Enemy stats, actions, AI scripts, battle text, models, textures | `battle/c0m*.dat` | partial: proved sections |
| Battle formations, stages, cameras, enemy slots, levels | `battle/scene.out` | all supported record fields |
| World cells, encounters, draw points, sky colours, rails, textures | `world.fs` / `wmx.obj`, `wmsetus.obj`, `rail.obj`, `texl.obj` | partial: proved fields |
| Scan text, card names, card texts, draw-point messages | `FF8_EN.exe` via FFNx overrides | partial: those tables |
| Field encounters, backgrounds, dialogue, scripts, walkmesh, gateways, INF header, cameras, movie frames | `field.fs` | locked: field models and media |
| Sound effects: preview, battle usage, per-sound replacement | `Data/Sound/audio.dat` + `audio.fmt` | replacement sounds need FFNx external SFX |
| FFNx display, audio, rendering, runtime settings | `FFNx.toml` | typed values in place |

## What is deliberately not editable, and why

The kernel publishes 599 of its 643 fields. The 44 held back are named
`unknown_*`, `padding_*` or `unused_*`, and each GF ability slot's `byte+0`,
whose schema entry records the audit that proved it dead: "genuinely DEAD, read
by nothing ... 0 field xrefs, 0 direct-address xrefs, AND all register-relative
accesses checked ... no aliases or bulk copies read it". A byte with no reader
has no proven meaning to write, so it stays visible and locked rather than
becoming a guess.

Two other limits come from the same rule:

- The executable is never modified. Its text tables are written as FFNx
  overrides instead (`ff8/en/exe/*.msd`), which is why the Data Map calls that
  entry partial rather than integrated.
- Model animation bytes have no proven writer, so they stay visible but locked
  (`codex/ff8/asset-tabs.md`). The Fields page edits movie frames but not field
  models.

## What the other tools cover

Surveyed from their own repositories on 2026-09-25:

- **Deling** (`myst6re/deling`, GPL-3.0, 51 stars): FF8 field and world-map
  *archive* editor. It opens the `Data/lang-*/*.fs` triplets, extracts nested
  field maps, and edits backgrounds, dialogue, scripts, walkmesh and
  encounters.
- **FF8 Ultimate Editor** (`HobbitDur/FF8UltimateEditor`, GPL-3.0, 12 stars):
  a suite. Its README lists Doomtrain (`kernel.bin`), Siren (`price.bin`),
  Junkshop (`mweapon.bin`), Quezacotl (`init.out`), Jumbo Cactuar
  (`Scene.out`), Ifrit and IfritGui (monster stats), IfritAI (monster AI, four
  views including its own scripting language), Seq (animation sequences), 3D
  (model view with glTF export), Texture and Dynamic Texture (textures and VRAM
  palette animation), Xlsx (monster stats to and from a spreadsheet), Cronos,
  Deling, Hyne and VincentTim.
- **Rinoa's Toolset** (`MaKiPL/FF8-Rinoa-s-Toolset`, 24 stars): battle stages
  with original-texture mixing and a real-time 3D view, world-map vehicles,
  world-map segments, train track visualiser and editor, GF environment
  objects, English dialogue decoding, a development-path searcher, a
  `Namedic.bin` editor, LZSS, an archive extractor, a Wm2field editor, a movie
  unpacker, TIM and TEX support, and UV layout display.
- **Jumbo Cactuar** (`Nihil-1/JumboCactuar`, 3 stars): a `Scene.out` editor
  with battle stage pictures.
- **IfritAI** (`HobbitDur/IfritAI`): monster AI, with a friendly view, a hex
  view, a raw-code view and its own code view.
- **Hyne** (`myst6re/hyne`, 81 stars): a save-file editor, not a game-data
  editor.

## How that maps onto this plugin

Covered, by the same file or the same table:

- `kernel.bin` data and its linked text (Doomtrain's area), `price.bin`
  (Siren), `mwepon.bin` (Junkshop), `init.out` (Quezacotl), `scene.out`
  (Jumbo Cactuar, plus stage and camera numbers), monster stats, monster AI
  scripts and battle text, refine and card-mod recipes, world cells and
  encounters, draw points, sky colours, train tracks, world textures, field
  backgrounds, dialogue, scripts, walkmesh, gateways, cameras and movie frames,
  and sound effects.
- Two things this plugin does that the older tools do not, both proved by their
  tests: mod files are merged per record rather than replacing a whole file
  (`worklog/100.md`), and every control carries help text that says what the
  value does in the game.

Not covered today, with what each would need:

- **World-map vehicle records** (Rinoa's Toolset edits them). No page reads that
  table; the sky-colour record's "vehicles" colour is a colour, not the vehicle
  table.
- **Wm2field** (Rinoa's Toolset). This plugin has Field to World (`wmset`
  section 9) and nothing for the world-to-field direction.
- **`Namedic.bin`** (Rinoa's Toolset). The Text tab inserts location, variable
  and key tokens from static tables in `kernel_text.editor_tokens()`, so the
  names behind those tokens are not editable here. The file's layout is proved
  and a reader and writer exist (`plugins/ff8/namedic.py`,
  `codex/ff8/namedic.md`, `tests/ff8/verify_ff8_namedic.py`); no page edits it
  yet, so the Data Map does not claim it.
- **Animation sequences** (Seq). Read and shown; no writer is proved.
- **Model export** (3D, glTF). The Models tab previews a model; it does not
  export geometry.
- **VRAM palette animation** (Dynamic Texture). Palettes can be previewed;
  the animated-VRAM effects are not editable.
- **Spreadsheet bulk import and export** (Xlsx). Every field is editable in the
  editor, but there is no spreadsheet round trip for a whole table.
- **Archive browse, extract and repack** (Deling). This plugin extracts what it
  needs from the installed game and writes only to the project copy; there is
  no archive management screen.
- **Save-file editing** (Hyne). Out of scope: a save is player state, not game
  data, and writing one is a different risk from writing an override.

## Keeping this true

The Data Map's own rows are the plugin's statement; if a reader or writer
changes what it covers, change the row in the same commit. This page records
the comparison, not the state of any single field.
