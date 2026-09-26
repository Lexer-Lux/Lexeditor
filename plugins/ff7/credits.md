# Final Fantasy VII format and runtime references

Lexeditor does not copy source code from the projects below. Their published
format/runtime behavior materially informed this plugin, so the exact role and
license are recorded here.

## Elena

Source: <https://github.com/Shojy/Elena>

MIT License

Copyright (c) 2019 Joshua Moon

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

## ff7tools

Source: <https://github.com/cebix/ff7tools>

Copyright (C) Christian Bauer <www.cebix.net>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

## Scarlet

Source: <https://github.com/petfriendamy/ff7-scarlet>
Reference revision used by the executable-data audit: `10a2283`

License: Microsoft Public License (MS-PL).

Scarlet's source was used as a reference for named, fixed-layout FF7 executable
data. Lexeditor does not bundle Scarlet or copy Scarlet source code.

## FFNx

Source: <https://github.com/julianxhokaxhiu/FFNx>
Direct Mode source revision used by the deployment implementation:
`b341cf135941ed745f89a5080a7cd95adb54018a`

Pinned setup release: `FFNx-v1.24.3.0` (tag `1.24.3`)
Upstream asset: `FFNx-Steam-v1.24.3.0.zip`
Published asset SHA-256:
`2be45f486974f0979b849d0525eb66427df62483ec99e9339e9773e9e52afc0d`

License: GNU General Public License v3.0 (GPL-3.0).

FFNx's source documents the Direct Mode paths and chunk loading behavior used
by `deployment.py`: KERNEL/KERNEL2 chunks, scene chunks, field section chunks,
and LGP-member overrides. FFNx's install guide also documents the 2026 Steam
working-directory setup that `tooling.py` follows. Lexeditor does not
redistribute FFNx bytes in the repository or installer: the setup action
fetches the exact upstream release asset, verifies its published SHA-256, and
refuses to replace a manual/7th-Heaven install or externally changed owned
files.

## 7th Heaven

Source: <https://github.com/tsunamods-codes/7th-Heaven>
Reference revision used by the read-only compatibility scanner:
`ae129f0bbeeeb236b1c37fb136e5fec25fd292a3`

License: Microsoft Public License (MS-PL).

7th Heaven's source documents the ordered active profile, `library.xml`
installed locations, folder and `.iro` mod forms, `mod.xml` ModFolder and
Conditional roots, and FFNx Direct Mode integration. Lexeditor uses that
published behavior only to inspect an explicitly configured 7thWorkshop tree
read-only. It never edits 7th Heaven state, does not guess inside `.iro`
packages, and does not choose a winner for overlapping external mod paths.

## 60/30 FPS Gameplay compatibility fixture

Source: <https://github.com/tangtang95/ff7-60fps-mod>
Reference revision used by the compatibility test:
`8195d9c0dc1a38a497ef7674f8e412936f11b120`

License: GNU General Public License v3.0 (GPL-3.0).

The public v1.15 `mod.xml` was used as an interoperability fixture for 7th
Heaven `ModFolder` / `ActiveWhen` profile-option behavior. Lexeditor does not
bundle this mod or its assets; the test builds a tiny synthetic folder tree
using only the proved metadata shape.

## Cover art

`assets/covers/ff7-remaster.png` is a custom composite stored in-tree because
it cannot be re-fetched. Photo source: Ersh_Zenith_01,
<https://www.reddit.com/r/FFVIIRemake/comments/1ex2kkp/what_bro_gonna_do/>
(image <https://i.redd.it/75syvh630vjd1.jpeg>). Logo and layout reference:
anidais, SteamGridDB grid 84563, <https://www.steamgriddb.com/grid/84563>
(image <https://cdn2.steamgriddb.com/grid/aeaa4605027b5a06c9113495302370d2.png>).
That reference cover is not stored; fetch it from SteamGridDB as needed.

## Theme assets (extracted locally, never redistributed)

The FF7 menu lettering and interface sounds come from the player's own
installation at prepare/serve time. Nothing below ships with Lexeditor:

- Menu font: `menu_us.lgp` member `usfont_h.tex` (12-pixel fixed grid,
  21 columns, FF7 text-code order). `game_font.py` builds a private
  `ff7-menu.ttf` in the game-data cache.
  Width and kerning are read from the English `window.bin` type-1 member;
  the palette separates letter ink from the dark shadow. Format research:
  [ff7tools retrieveMetrics](https://github.com/cebix/ff7tools/blob/master/trans)
  and [charWidth](https://github.com/cebix/ff7tools/blob/master/ff7/ff7text.py)
  (ISC; no implementation code copied).
- Interface sounds: numeric records from the installed `audio.fmt` /
  `audio.dat` pair, decoded to the private `theme-sfx` cache by the shared
  `theme_sounds` module (FF7 format). The slot mapping (confirm/move 1,
  save 2, back/exit 4) is the mapping `server.py` serves.
