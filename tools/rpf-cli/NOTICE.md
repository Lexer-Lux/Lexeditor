# Bundled RDR2 RPF command-line tool

Lexeditor runs this tool as a separate process. It reads RDR2 archives and
writes selected files to Lexeditor's private data cache. It does not write to
the game installation.

Source: `https://github.com/amrshaheen61/RDR2-RPF-Tool`

Base commit: `6da402a7db476b0e9ce3717aa7d7a016c7704dfb`

The `RpfCli` wrapper adds command-line list and extract operations and a
read-only file-share change. The corresponding source is in `source/`. The
AGPL-3.0 license is in `LICENSE.txt`.

Version 1.1 adds nested extraction chains, prefix or folder extraction,
RBF-to-XML output, and correct handling of signature-protected RPF8 entries.
Such entries exclude the final 256-byte signature allowance from their stored
size, but their payload still starts at the entry's recorded offset.

Version 1.3 adds self-contained RDR2 PSO-to-XML conversion for direct files and
entries reached through nested extraction chains. The converter reads RDR2's
extended PMAP table, 20-bit packed PSO pointers, the RDR2 enum and flag widths,
and the fixed-capacity structure arrays used by weapon data. It preserves
unresolved schema hashes as stable XML names.

`bin/names.txt` is the name table used by the tool. `bin/oo2core_5_win64.dll`
is the runtime compression library included with the upstream tool.

The RBF-to-XML support uses MIT-licensed RageLib code from
`https://github.com/WesternSpace/gta-toolkit` at commit
`97bb07ef9190bea97a943f92e2c10f5cd946ce7b`. The exporter writes RDR2
`type` and `content` attributes before child elements so valid XML is produced
when those descriptors occur late in the RBF structure. Its license is in
`RAGELIB-LICENSE.txt`. RDR2 can reuse one RBF descriptor name with different
value types; the type byte stored on each value is authoritative.

The PSO reader, value wrappers, and the six bundled `pso-names` lists also use
MIT-licensed RageLib / gta-toolkit material from the same repository and commit.
Lexeditor's wrapper adds the RDR2 format corrections and the small explicit
catalog/weapon field-name contract needed by its active editor pages.
