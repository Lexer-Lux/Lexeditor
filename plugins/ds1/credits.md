# Dark Souls Remastered

Smithbox by Vawser and contributors supplied the reference for the Steam app ID
and executable name. Reviewed official source at commit
`057b417887cc7d0ddc8001602be3f5339f42c74f`, specifically
`src/Smithbox.Program/Editors/Project Editor/GUI/ProjectConfigureMenu.cs`.
Repository: https://github.com/vawser/Smithbox

This plugin uses Lexeditor's existing installation discovery, shared shell,
and fixed-field PARAM reader. DS1 item, NPC, attack, behavior and projectile definitions, English annotations,
row names and enums are selectively vendored from Smithbox under MIT.
Exact source paths and upstream hashes are in `metadata/SOURCE.json`.
No Smithbox executable implementation, dependencies, binaries, or GPL code
are copied. The upstream MIT notice covers the redistributed metadata.

TKGP / JKAnderson's SoulsTemplates BND3.bt and DCX.bt at commit
`f1d114a3668e3c97a1ace82411158df6b3bc50a4` supplied archive format facts.
These templates are Apache-2.0 licensed; no template code is redistributed.
https://github.com/JKAnderson/SoulsTemplates

Smithbox's SoulsFormats dependency was inspected as a research reference,
found to be GPL-3.0, and excluded. It is not bundled, linked, or invoked.

## Stamina recovery effects (stamina.py)

Smithbox's DS1R `Defs/SpEffect.xml` at the same pinned revision supplied the
368-byte special-effect row layout and signed recovery modifier at `0xB8`.
Paramdex contributors' `DS1R/Names/SpEffectParam.txt`, blob
`77e53462c28ea28e1abb140eea29d177da8bff74`, supplied reference identities such
as Grass Crest Shield 6890 and the armour-piece penalty groups.
https://github.com/soulsmods/Paramdex

Metal-Crow and Dark-Souls-1-Overhaul contributors' `SpEffectEditor-Remaster.CT`
at revision `2a3d8cbe2acee663bef03c7be4f968dbb68f951f` independently confirmed
the recovery field's four-byte `+B8` layout. This is a factual cross-check;
no Cheat Engine, injection or other upstream executable code is copied.
https://github.com/metal-crow/Dark-Souls-1-Overhaul

Implementation, compatibility limits, exact source paths and the unresolved
native-baseline investigation are documented in `stamina-sources.md`.
Only original code, reference identities and synthetic tests are added.

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
