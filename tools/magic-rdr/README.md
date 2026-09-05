# MagicRDR read-only bridge

Lexeditor uses `app/Rpf6ReadCli.exe` to list and extract Red Dead Redemption
RPF6 files. The bridge opens source archives with read access only. It uses the
MagicRDR 1.3.10 release from `Foxxyyy/Magic-RDR` and its public RPF6 API.

Pinned release archive SHA-256:
`d66af304a94282b22a475a5f9aabc67e8d6bd5a4263ba895502124e31a3083ea`.

Commands:

```text
Rpf6ReadCli list <archive.rpf> [wildcard]
Rpf6ReadCli extract <archive.rpf> <output-directory> [wildcard]
```

MagicRDR has no declared repository license. Keep this dependency local to the
private Lexeditor installation unless its author supplies redistribution terms.
