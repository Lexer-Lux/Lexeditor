# FF8 SFX, Models, and Textures asset knowledge

Settled facts behind the SFX, Models, and Textures tabs. Research-first
sources are credited in `ui/credits-sources.json` under the `ff8` plugin;
this page records what was proved and what stays unknown.

## Tools surveyed

- **Deling 1.1.0** (`myst6re/deling`, GPL-3.0-or-later): FF8
  field/world-map archive editor. Installed at
  `D:\Downloads\deling-1.1.0-win64\` and running during research. It opens
  the `Data/lang-en/*.fs` triplets, extracts nested field maps, and edits
  backgrounds, dialogue, scripts, walkmesh, and encounters. It does not
  manage FFNx external SFX/texture overrides, which is the gap the asset
  tabs fill.
- **FF8 Ultimate Editor** (`HobbitDur/FF8UltimateEditor`, GPL-3.0):
  kernel/enemy/AI/text editing plus the Ifrit model viewer and Julia sound
  work. The plugin already vendors its LZS decoder.
- **FF8 Modding Wiki** (`HobbitDur/FF8ModdingWiki`): the canonical format
  reference for audio.fmt, battle `.dat` sections, MCH field models, and
  TIM textures. Specific pages are named below.
- **FFNx** (`julianxhokaxhiu/FFNx`, GPL-3.0): the runtime that loads every
  override these tabs write. Its `src/sfx.cpp`, `src/audio.cpp`, and
  `src/ff8/vram.cpp` define the override file names; the tabs only claim
  mappings proved by that source.
- **Roses and Wine** (DLPB): a full music replacement (looping OGG music
  via bass.dll). It replaces streamed music, not `audio.dat` sound
  effects, so it is out of scope for the SFX tab.
- **OpenVIII** (MIT, already credited): world-map and texture references.

## SFX: `Data/Sound/audio.fmt` + `audio.dat`

From the wiki
([Audio](https://github.com/hobbitdur/ff8moddingwiki/blob/HEAD/FF8/TechnicalReference/Miscellaneous/FileFormat_FMT.md)):

- `audio.fmt` starts with a u16 `soundCount`, then `soundCount + 1`
  variable-length entries. Entry 0 is a blank placeholder; the sound id
  used everywhere else in the engine is the 0-based entry index.
- Each entry is a 20-byte locator record (`dataLength`, `dataOffset`,
  `bufferFlags` where 1 means looping, padding, DirectSound cursors)
  followed by a standard 18-byte `WAVEFORMATEX` plus `cbSize` extra bytes.
- `audio.dat` is a raw concatenation of waveform bodies with no per-sound
  header. Retail facts: 2791 entries, 1544 valid sounds, every valid sound
  MS-ADPCM 44100 Hz mono.
- A standalone WAV wraps the entry bytes: `RIFF + u32(dataLength + 38 +
  cbSize) + WAVE + fmt-chunk + data-chunk`. The plugin instead decodes
  MS-ADPCM to PCM16 for browser playback (same decoder as theme sounds).

FFNx external SFX names, proved by `src/sfx.cpp`
`ff8_sfx_play_layered` (numeric `id` is the audio.fmt index):

- field: `<field>_<triangle>_<id>`, then `<field>_<id>`
- menu: `menu_<id>`; world map: `world_<id>`; battle: `battle_<id>`
- global fallback: `<id>`

Each name resolves to `<external_sfx_path>/<name>.<ext>` (`src/audio.cpp`
`getFilenameFullPath`), trying every configured extension. A mod file
claims sound id N when its stem is `N` or ends in `_<N>` with a
battle/menu/world/known-field prefix. Anything else in a mod's `sfx/`
folder is shown as an unrecognized SFX file, never silently dropped.

Proven sound semantics (shown as "used by" notes, not names):

- The wiki's [battle actor sound table](https://github.com/hobbitdur/ff8moddingwiki/blob/HEAD/FF8/TechnicalReference/Battle/BattleActorSounds.md) maps each battle actor
  `com_id` to up to 7 decoded audio ids. Playable characters are
  `0x00`-`0x0A` (Squall, Zell, Irvine, Quistis, Rinoa, Selphie, Seifer,
  Edea, Laguna, Kiros, Ward); `0x11`-`0x9F` are monsters.
- The `loop` flag comes from each entry's `bufferFlags`, which FFNx reads
  from the loaded `audio.fmt`.

Unknown: plain-language names for most sound ids. Rows show `Sound <id>`
plus proven usage; nothing is invented.

## Models: battle `.dat` files

From the wiki
([Monster files](https://github.com/hobbitdur/ff8moddingwiki/blob/HEAD/FF8/TechnicalReference/Battle/MonsterFiles.md),
[Character & weapon files](https://github.com/hobbitdur/ff8moddingwiki/blob/HEAD/FF8/TechnicalReference/Battle/CharacterWeaponFiles.md)):

- The header is a u32 section count plus a position table and a trailing
  end offset. The on-disk count uses the +1 convention shared with the
  enemy editor: a raw value of N means N section positions plus the end
  offset (N+1 table entries).
- Monsters (`c0mNNN.dat`) carry 11 sections: skeleton, model geometry,
  model animation, dynamic texture data, animation sequences, camera
  sequence, information & stats, battle scripts/AI, sounds, sound sample
  bank, textures. `c0m127.dat` is the documented 2-section exception
  (info & stats + AI only; invisible Apocalypse trigger).
- Playable characters are composites of a body (`dXcYYY.dat`) and a weapon
  (`dXwYYY.dat`) file with the same section building blocks in a different
  numbering; the animation-sequence program lives in the weapon file.
- Geometry sections expose object/vertex/primitive counts (see
  [Model geometry](https://github.com/hobbitdur/ff8moddingwiki/blob/HEAD/FF8/TechnicalReference/Battle/Model%20Sections/ModelGeometry.md));
  the Textures section holds standard PlayStation TIMs (count + offsets +
  complete TIM blocks).
- The AKAO sound sections (9-10) are parsed by the PC engine but never
  played; battle sounds come from the actor sound table above.
- `c0mNNN` numbering matches the enemy-table index (`schema/monster.json`
  `com_id`); the wiki battle `com_id` is that file's `entity_id`.

FFNx loads whole-file `direct/battle/*.dat` overrides, so whole-file
replace/export/revert is the editor granularity. Geometry, skeleton, and
animation bytes have no proven writer and stay visible-but-locked. The
animation-sequence section's container is proved (count, one offset per id,
then the byte code; `/api/animation-sequences?file=c0m001.dat`), but the byte
code inside it is still only counted, so that row stays locked too.

Out of scope: battle stages (`a0stg*.x`), magic-effect files (`mag*`),
field MCH/`chara.one` models, and world-map models. Stage/magic archive
entries are listed as locked rows from the `battle.fl` index without
extracting their bytes.

## Textures: TIMs and FFNx external names

TIM layout follows the standard PlayStation format (magic `0x10`,
BPP/CLP flags, optional CLUT block, image block sized in 16-bit
frame-buffer pixels; 4-bit and 8-bit indexed plus 16-bit direct are
decoded for previews).

FFNx external texture base names, proved by `src/ff8/vram.cpp`:

- `battle/<battle filename>` for battle archive textures
- `world/dat/texl/texture<N>` for world-map texl TIMs
- `field/model/main_chr/<name>-<n>` for field main-character textures
- `field/mapdata/<sub>/<field>/<field>_<n>` for field backgrounds
- `magic/<file>`, `cardgame/...`, `world/esk/chara_one/model<id>-<tex>`

The palette/variant suffix FFNx appends when dumping is not replicated
here, so a mod PNG is attributed to the vanilla asset whose verified base
path it extends, and the matched filename is always shown as evidence.
Mod files under any other path are listed as unmapped mod textures with an
explicit note; they are never hidden and never attributed to an asset.

The 20 world texl TIMs keep their existing validated editor under
Maps > World; the Textures tab previews them and links there instead of
growing a second editor. Field backgrounds likewise stay edited under
Maps > Field.

## Research 8-8: Deling's "Additional characters" tab (not implemented)

Deling's "Additional characters" tab is `TdwWidget`
(`src/widgets/TdwWidget.h`, `tabName() == "Additional characters"`). It
edits the per-field-map `.tdw` additional-font file
(`TdwFile::filterText() == "Field additionnal fonts PC file (*.tdw)"`),
not NPC or playable-character placement. Lexeditor's script-label-only
view of field entities is unrelated to this tab.

Format, proved by Deling `src/files/TdwFile.cpp` (GPL-3.0-or-later):

- u32 `posHeader` (always 8), u32 `posData`, then packed 4-bit
  character widths (112 bytes per 224-character table, low nibble
  first), then a standard 4-bit TIM with 8, 16, or 32 palettes (8 text
  colours: dark grey, grey, yellow, red, green, blue, purple, white).
- Glyphs are 12x12 pixel cells in a 21-column grid. Deling paints
  individual glyph pixels, edits one width nibble per character, and
  imports whole sheets; the tab previews the sheet in each colour.

Retail facts, probed from the installed `Data/lang-en/field.fs`:

- 879 of 896 field-map triplets ship a `<map>.tdw` (about 2 KB each).
- Every shipped file is small: 635 carry one partial table (up to a
  few dozen characters), 244 carry palettes only (empty header, zero
  tables). None uses more than one table.
- Decoded samples render Japanese kanji: these are the extra glyphs a
  field's dialogue needs beyond the main menu font.

Safety and scope proposal (implementation explicitly out of scope):

- Same-count pixel and width edits are the safe core: the format is
  fully mapped, cell geometry is fixed, and the file would save
  through the existing per-asset field pipeline
  (`direct/field/mapdata/<group>/<name>/<map>.tdw`), next to the
  dialogue and script overrides. In-game verification is still needed.
- Count-changing edits (new glyphs or tables) wait until MSD
  table/character references are mapped; Lexeditor's MSD decoder does
  not document table-switch codes yet, so nothing may renumber the
  characters existing lines reference.
- Proposed slice: per-map read-only glyph-grid preview first, then
  pixel/width editing at a fixed character count with no-op-exact
  saves, reusing the TIM decoder behind the Textures tab. Deling
  stays the reference implementation; no Deling code is vendored.
