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

Fahrenheit documents file-only mods, `<mod>.manifest.json`, `mods/loadorder`, and the External File Loader roots `efl/x` and `efl/x2`. No Fahrenheit source or binary is bundled by this plugin.

## FFXDataParser and VBFTool

The following public reverse-engineering projects were used as research cross-checks only; their code is not copied or distributed by Lexeditor:

- https://github.com/Karifean/FFXDataParser
- https://github.com/topher-au/VBFTool
