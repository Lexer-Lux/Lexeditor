# Final Fantasy VII format and runtime references

Lexeditor does not bundle or copy code from the projects below. Their published
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

License: GNU General Public License v3.0 (GPL-3.0).

FFNx's current source documents the Direct Mode paths and chunk loading behavior
used by `deployment.py`: KERNEL/KERNEL2 chunks, scene chunks, field section
chunks, and LGP-member overrides. Lexeditor does not bundle FFNx in this change;
a pinned binary helper bundle remains a separate delivery requirement because
the available repository write interface is text-only.
