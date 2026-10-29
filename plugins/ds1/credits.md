# Dark Souls Remastered

Smithbox by Vawser and contributors supplied the reference for the Steam app ID
and executable name. Reviewed official source at commit
`057b417887cc7d0ddc8001602be3f5339f42c74f`, specifically
`src/Smithbox.Program/Editors/Project Editor/GUI/ProjectConfigureMenu.cs`.
Repository: https://github.com/vawser/Smithbox

This plugin uses Lexeditor's existing installation discovery, shared shell,
and fixed-field PARAM reader. DS1 item, NPC, attack, behavior, projectile, effect and scaling-curve definitions, English annotations,
row names and enums are selectively vendored from Smithbox under MIT.
Exact source paths and upstream hashes are in `metadata/SOURCE.json`.
No Smithbox executable implementation, dependencies, or binaries
are copied. The upstream MIT notice covers the redistributed metadata.
GPL reuse, where used, is credited per file below with its license.

TKGP / JKAnderson's SoulsTemplates BND3.bt and DCX.bt at commit
`f1d114a3668e3c97a1ace82411158df6b3bc50a4` supplied archive format facts.
The same revision's MSB/MSB1 templates (MSB1.bt, Model.bt, Part.bt, by
Meowmaritus and TKGP) supplied the map layout facts behind `msb.py`,
including the Part.bt type-data blob sizes placement duplication copies.
These templates are Apache-2.0 licensed; no template code is redistributed.
https://github.com/JKAnderson/SoulsTemplates

Smithbox's SoulsFormats dependency is GPL-3.0 (license file verified).
Lexer allows GPL code in this repo: the combined app ships under GPL
terms, with license files riding the per-plugin credits automation.
(An earlier agent note claimed GPL excluded; that was never Lexer's
decision.)

## Event-script composition (emevd.py)

DS1 EMEVD layout facts were checked against TKGP / JKAnderson's SoulsFormats,
`SoulsFormats/Formats/EMEVD/{EMEVD,Event,Instruction,Parameter,Layer}.cs`.
Its repository license is GPL-3.0. This bounded DS1 reader, writer and event-ID
composer are an original implementation; no upstream code is redistributed.
https://github.com/JKAnderson/SoulsFormats

## Named texture composition (texture_packs.py)

PC TPF directory and encoding facts were checked against TKGP / JKAnderson's
SoulsFormats, `SoulsFormats/Formats/TPF/TPF.cs` (`Read`, `Texture.WriteHeader`,
`WriteName` and `WriteData`). Its repository license is GPL-3.0. The reader,
writer and record-comparison implementation here are original; no upstream
code is redistributed.
https://github.com/JKAnderson/SoulsFormats

## Animation events (tae.py)

The TAE container layout (header, animation table, event headers,
timestamp pool) comes from the same revision's TAE3.bt and
TAE3_EventData.bt templates (Apache-2.0, by TKGP), translated to the
32-bit DS1 form and verified against every animation file in every
readable character binder. No template code is redistributed.
Event-type meanings and parameter facts were paraphrased from the
soulsmodding wiki's format:tae page (CC BY-SA),
http://soulsmodding.wikidot.com/format:tae, and confirmed against
measured value distributions across the installed game before any
field was exposed. DSAnimStudio's DS1 event template
(Meowmaritus/DSAnimStudio) served as a read-only cross-check for
field order and sizes; none of its text, names, or code is reused.

## Models (flver.py)

The FLVER2 byte layout (header, dummy, material, bone, mesh, face set,
vertex array, layout member and texture structs, vertex semantic and
format ids, triangulation, UV/normal/weight codecs, and the DS1R QLOC
layout repairs) comes from soulstruct by Grimrukh (GPL-3.0-or-later,
license declared in pyproject.toml; no LICENSE file upstream),
specifically `src/soulstruct/flver/` at version 2.6.0:
https://github.com/Grimrukh/soulstruct
No soulstruct code is redistributed: `flver.py` is a from-scratch
struct reader of the same layout. Verified against all 1752 standalone
map models in the installed game (13,407 meshes, zero failures).

## Map viewport (viewport.js, three.module.js, orbit-controls.js, transform-controls.js)

The 3D viewport renders with three.js r170 (MIT) by Three.js authors,
vendored as published (unminified ESM) from
https://github.com/mrdoob/three.js
OrbitControls drives the camera and TransformControls drives the
placement move gizmo.

MIT License

Copyright (c) 2010-2024 Three.js Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Animation playback (hkx.py)

The TAG0 tagfile container (sections, packed integers, the type
table, items and typed objects) and the hkaSkeleton,
hkaSplineCompressedAnimation, hkaAnimationBinding and
hkaDefaultAnimatedReferenceFrame field maps come from
SoulsAssetPipeline by Meowmaritus (GPL-3.0-or-later),
Havoc/IO/Tagfile and SoulsAssetPipeline/Animation/HKX at commit
d11caf9 (2026-05-19):
https://github.com/Meowmaritus/SoulsAssetPipeline
The spline sampler follows the same project's SplineCompressedAnimation
reader, adapted from HavokLib by PredatorCZ (GPL-3.0-or-later):
https://github.com/PredatorCZ/HavokLib
No upstream code is redistributed: `hkx.py` is a from-scratch reader
of the same layout. Verified against the installed game: 11,604 files parsed and 9,832 animations sampled (657,500 frames, 143 multi-block), zero errors, unit quaternions throughout.

## Native param replacement (deployment.py)

No mod loader is bundled or invoked. The finding that Dark Souls Remastered
reads param/GameParam/GameParam.parambnd.dcx as a loose file came from direct,
read-only inspection of an installed copy (param/, map/, chr/, sound/ etc. are
ordinary folders, not a packed archive), corroborated by the published
documentation of Nordgaren/UXM-Selective-Unpack (MIT-style community tool,
https://github.com/Nordgaren/UXM-Selective-Unpack) and its predecessor
JKAnderson/UXM (https://github.com/JKAnderson/UXM), both of which note that
Dark Souls Remastered needs no unpacking because it ships unpacked already.
No UXM code, binaries, or dependencies are used; this is a factual reference
only, consulted to confirm a design decision before implementing it.

## DSR Mod Engine profile backend (modengine_profile.py)

The profile exporter targets AltimorTASDK's Dark Souls Remastered branch of
soulsmods/ModEngine2, pinned at
`76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d`:
https://github.com/AltimorTASDK/ModEngine2/tree/76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d

The reviewed `LICENSE-MIT` permits reuse with its required notice. Material
references are `launcher/launcher.cpp`,
`installer/dist/config_darksoulsremastered.toml`, and
`src/modengine/ext/mod_loader/archive_file_overrides.cpp`. They establish the
DSR target, configuration shape and first-matching-root precedence. The exporter
reverses its low-to-high source order and places its merged overlay first.
No Mod Engine implementation code, executable, DLL or dependencies are copied,
bundled or invoked in this draft. The native runtime still requires packaging,
license/notices review for its dependencies and installed-game verification.

`composition.py` is a separate baseline-aware merger using the existing DS1
reader and serializer; Mod Engine itself does not merge edits within one
archive. The upstream launcher also needs its explicit-path and adjacent-game
path assumptions corrected for DSR before delivery. See `MOD_LOADER.md` for the
exact support contract and unfinished runtime/UI/real-mod acceptance gates.

MIT License

Copyright (c) 2025 Vawser
Copyright (c) 2018 Katalash, Meowmaritus

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Executable tweak loader

Lexeditor combines DS1 tweak mods' native patches onto the vanilla
executable (`exe_patches.py`). Microsoft's PE/COFF and x64 exception-handling
documentation supplied the format facts; no implementation code is copied:
- https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
- https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64

## Menu layout (menu_layout.py)

The DRB section order, entry sizes and text-shape encodings were measured by
read-only inspection of the installed Remastered `menu/menu.drb.dcx`; see
`codex/ds1/menu-layout.md`. No third-party code is used. The DCX wrapper reuses
the SoulsTemplates DCX facts above.

Each tweak's own credits travel with its mod.

## Debug mode (runtime/lexeditor_ds1_debug.c)

The debug loader links dearxan 0.5.6 by tremwil, dual-licensed MIT and
Apache-2.0, from its official release `dearxan-0.5.6.zip`. dearxan neuters
Arxan (GuardIT) in FromSoftware games so a debugger can attach; it is linked
only into the debug loader (`runtime/package/debug/dinput8.dll`), never the
everyday one. https://github.com/tremwil/dearxan

me3's write-up on Arxan in FromSoftware games described why debuggers and
breakpoints end the game. https://me3.help/en/latest/blog/posts/arxan-reversing-1/

## Theme (title art, menu fonts, interface sounds)

The editor's Dark Souls look comes from the player's own installation and is
never redistributed: the `Title` texture from
`menu/<language>/menu_local.tpf.dcx` (rendered to PNG through the TPF/DDS
preview pipeline), the menu font sources under `font/<language>/`
(`DSFont24.ccm.dcx`, `TalkFont24.ccm.dcx` and `*.fnt`), and the interface
sound banks `sound/frpg_sm*.fsb` and the menu bank `sound/frpg_main.fsb`,
with their `.fev` event projects.
`plugins/ds1/theme.py` extracts these into a private cache outside the
checkout at serve time.

The `font/<language>/` layout follows the public ccm-changer notes:
https://github.com/binamselerimir/ccm-changer
FSB4 bank inventory (magic, stream count, 80-byte sample headers) was
measured by read-only inspection of the installed banks; no FMOD code or
documentation is copied. Stream payloads proved out as padded MPEG Layer III, mostly MPEG-1 with MPEG-2 in the menu bank (see `plugins/ds1/fsb.py`), extracted without copying any decoder. Bitmap-to-webfont conversion
is not integrated yet, so headings use an engraved serif fallback. Menu UI events map from proved FEV event paths (`/frpg_main/CURSOL_MOVE` and siblings) to shell sound slots; exit/save have no proved source and stay silent.
