# RpfCli 1.3

`RpfCli` is Lexeditor's read-only, command-line RPF8 extractor. It can list an
archive, extract one entry, follow nested RPF8 archives, and convert RBF or PSO
data to editable XML or an RSC8 text database to JSON. It never writes to the game
installation.

## Commands

```text
RpfCli --version
RpfCli <archive.rpf> --list [filter]
RpfCli <archive.rpf> --list-chain <entry> [nested-entry ...]
RpfCli <archive.rpf> --list-content
RpfCli <archive.rpf> --extract-selected <output-directory> <entry> [entry ...]
RpfCli <archive.rpf> <entry> <output>
RpfCli <archive.rpf> --extract-chain <entry> [nested-entry ...] <output>
RpfCli <archive.rpf> --extract-chain-xml <entry> [nested-entry ...] <output.xml>
RpfCli <archive.rpf> --extract-chain-pso-xml <entry> [nested-entry ...] <output.xml>
RpfCli <archive.rpf> --extract-chain-text-json <entry> [nested-entry ...] <output.json>
RpfCli <archive.rpf> --extract-prefix <prefix> <output-directory>
RpfCli --rbf-to-xml <input.ymt> <output.xml>
RpfCli --pso-to-xml <input.ymt> <output.xml>
RpfCli --yldb-to-json <input.yldb> <output.json>
```

For example, this command reads the current pause-menu asset through its nested
archive and writes editable XML:

```text
RpfCli update_4.rpf --extract-chain-xml x64/data/ui/screens.rpf pause/indices/root_index.ymt root_index.xml
```

Version 1.3 converts RDR2 `PSIN` resources, including `catalog_sp.ymt` and the
base and layered weapon files used by Lexeditor. It uses the PSO schema stored
inside each file. Names required by Lexeditor's catalog and weapon data
contracts are explicit. Other unresolved hashes use stable
`UNK_MEMBER_0xXXXXXXXX` names so an editor save does not discard those nodes.

`--extract-prefix` exports every named entry below one archive path. It keeps
the selected folder name and its internal directory structure under the output
directory. Output paths are confined to that directory.

`--list-chain` follows one or more nested RPF8 entries and lists the final
archive. It does not extract the listed files.

`--extract-selected` opens one archive and extracts only the named entries in
one pass. Output paths stay inside the selected output directory.

See `NOTICE.md`, `LICENSE.txt`, and `RAGELIB-LICENSE.txt` for provenance and
licenses.
