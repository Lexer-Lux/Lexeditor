# Red Dead Redemption 2 third-party credits

Lexeditor's Red Dead Redemption 2 plugin vendors model-decoding and hooking libraries, and relies on external runtimes that are never redistributed. All plugin-local notices are quoted in full below; shared-tool notices live with their tools (see the last section).

## Attributions

- **Sage of Mirrors** — PyLibDrawable/libdrawable model geometry and texture-reference decoding. <https://github.com/Sage-of-Mirrors/PyLibDrawable>
- **RDR2 RPF Tool contributors** — Read-only resource archive extraction. <https://github.com/amrshaheen61/RDR2-RPF-Tool>
- **RageLib contributors** — Resource format support used by the archive tool. <https://github.com/WesternSpace/gta-toolkit>
- **Tsuda Kageyu / MinHook contributors** — Vendored minimal x86/x64 Windows API hooking library used by the RDR2 native runtime. <https://github.com/TsudaKageyu/minhook>
- **Alexander Blade / ScriptHookRDR2** — External runtime loader required by the RDR2 native ASI; not redistributed by Lexeditor. <https://www.dev-c.com/rdr2/scripthookrdr2/>
- **Smerdokryl / RDR2_SDK** — External ScriptHookRDR2 SDK headers and import library used to build the RDR2 native runtime; not redistributed by Lexeditor. <https://github.com/Smerdokryl/RDR2_SDK>

## License notices

### PyLibDrawable — source notice

LEXEDITOR uses PyLibDrawable and libdrawable by Sage of Mirrors under the MIT
license inlined below to read RDR2 YDR geometry and shader references.

`pylibdrawable.pyd` is built for CPython 3.10 from PyLibDrawable commit
`a42e4d8df7f9e35ee81a88cbdf7cb51ae15a3c4a` and its pinned libdrawable commit
`f44016f07a7308347b62ee861bbfb10270817fc1`. LEXEDITOR adds one small extension:
the binding exposes the external texture names already stored in each shader.
Its SHA-256 is
`9DF27F2AF114E95AB4619798B578104D74D4A74610D9AFFAD6EA113C071D6E70`.

`pylibdrawable_geometry_beta2.pyd` preserves the prior unmodified
RedDead2Blend v0.0.2 binary. Its SHA-256 is
`F32D78F5302B79DAB392557F0319F7BE3E5267686D2196A52DA8A22D63F94021`.

Sources:

- https://github.com/Sage-of-Mirrors/PyLibDrawable
- https://github.com/Sage-of-Mirrors/librdr3
- https://github.com/Sage-of-Mirrors/RedDead2Blend/releases/tag/v0.0.2

### PyLibDrawable — MIT License

MIT License

Copyright (c) 2023 Dylan Ascencio

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

### MinHook — BSD 2-Clause License

MinHook - The Minimalistic API Hooking Library for x64/x86
Copyright (C) 2009-2017 Tsuda Kageyu.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

 1. Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.
 2. Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER
OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

================================================================================
Portions of this software are Copyright (c) 2008-2009, Vyacheslav Patkov.
================================================================================
Hacker Disassembler Engine 32 C
Copyright (c) 2008-2009, Vyacheslav Patkov.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

 1. Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.
 2. Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

-------------------------------------------------------------------------------
Hacker Disassembler Engine 64 C
Copyright (c) 2008-2009, Vyacheslav Patkov.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

 1. Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.
 2. Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

### RPF tool and RageLib notices

These live with the shared tools and are embedded in the Credits bundle from:

- `tools/rpf-cli/NOTICE.md`
- `tools/rpf-cli/LICENSE.txt` (AGPL v3)
- `tools/rpf-cli/RAGELIB-LICENSE.txt` (MIT)
