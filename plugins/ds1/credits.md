# Dark Souls Remastered

Smithbox by Vawser and contributors supplied the reference for the Steam app ID
and executable name. Reviewed official source at commit
`057b417887cc7d0ddc8001602be3f5339f42c74f`, specifically
`src/Smithbox.Program/Editors/Project Editor/GUI/ProjectConfigureMenu.cs`.
Repository: https://github.com/vawser/Smithbox

This plugin uses Lexeditor's existing installation discovery, shared shell,
and fixed-field PARAM reader. DS1 item definitions, English annotations,
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
