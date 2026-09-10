# FFX/X-2 research references and notices

Lexeditor does not bundle proprietary FINAL FANTASY X/X-2 data. Installed VBFs are treated as read-only source archives.

## michivi/vbf-fs

Lexeditor's clean Python VBF reader was implemented from the documented behavior and BSD-licensed source of **michivi/vbf-fs**:

- https://github.com/michivi/vbf-fs
- License: BSD 3-Clause

The reference establishes the `SRYK` header, entry/name/block tables, 64 KiB block model, zlib-compressed block handling, and trailing MD5 validation used by this plugin.

Copyright 2020 Michivi

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## Fahrenheit

**fahrenheit-crew/fahrenheit** is the interoperability reference and deployment/runtime boundary for this plugin:

- https://github.com/fahrenheit-crew/fahrenheit
- License: LGPL-3.0-or-later

Fahrenheit documents file-only mods, `<mod>.manifest.json`, `mods/loadorder`, the External File Loader roots `efl/x` and `efl/x2`, and the Stage 0 launch contract used by the explicit Play actions. No Fahrenheit source or binary is bundled by this plugin.

## FFXDataParser

**Karifean/FFXDataParser** is used only as a public reverse-engineering cross-check; its source is not copied or distributed by Lexeditor:

- https://github.com/Karifean/FFXDataParser

For the conservative FFX ability-animation family, it independently identifies `command.bin`, `item.bin`, `monmagic1.bin`, and `monmagic2.bin` as the same command-data layout family, reads the two animation IDs at record offsets `+0x10/+0x12`, uses `0x60` records for player-command/item tables, and `0x5C` records for the two monster-magic tables.

It is also a research cross-check for the FFX fixed-record container, the FFX-2 u32 fixed-record container, and other explicitly documented structured fields used by this plugin.

## FFXProjectEditor

**osdanova/FFXProjectEditor** is a second independent format cross-check; its source is not copied or distributed by Lexeditor:

- https://github.com/osdanova/FFXProjectEditor

Its project paths identify the English/US FFX `new_uspc/battle/kernel` files `command.bin`, `item.bin`, `monmagic1.bin`, and `monmagic2.bin`. Its serialized ability layout places four four-byte text references before the animation IDs and distinguishes the four-byte player extension used by command/item records from monster-magic records, independently agreeing with the `+0x10/+0x12`, `0x60`, and `0x5C` facts above.

## FFX2-010-Templates

**HeartlessSeph/FFX2-010-Templates** is used as an independent factual cross-check for the FFX-2 `accessory.bin` record layout; its template source is not copied into Lexeditor:

- https://github.com/HeartlessSeph/FFX2-010-Templates

## VBFTool

**topher-au/VBFTool** is a historical VBF and Steam-layout research cross-check only; its source is not copied or distributed by Lexeditor:

- https://github.com/topher-au/VBFTool
