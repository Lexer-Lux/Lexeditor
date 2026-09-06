# Archive extraction tooling

`_downloads/RPF8_TOOL/Rpf8Extract.exe` — usage:
`Rpf8Extract <archive.rpf> <entry> [nested-entry ...] <output>`. Passing no
arguments prints the usage line; there is no list mode.

**Its "Distroy File: <path>" output is a misspelled handle-close message, not
damage.** It prints the SOURCE archive path immediately after a successful
extraction and looks alarming every time. It has now caused a panic more than
once. The source archive is untouched — check size and mtime if unsure, but do
not treat this line as an error and do not stop work over it.

What it can and cannot do:
- CAN pull a nested archive out as a raw blob: it extracted `0x800AFF13.rpf`
  (774,164,666 bytes) out of `update_2.rpf` successfully.
- CANNOT read inside that nested archive. It is encrypted (the index at
  `_downloads/extract/update_2-keys.tsv` marks it `Encrypted;`), the extracted
  blob has no RPF magic, and every build — `Rpf8Extract.exe`, `.new.exe`,
  `.key.exe`, `.raw.exe` — throws in `RPF8.Load` on it.
- Entry names inside nested archives are hashed, not plain paths. Plain-path
  lookups and plain-JOAAT-of-the-name lookups both fail, so the scheme is not
  simple JOAAT.

Tools that CANNOT substitute for OpenIV here, each tested rather than assumed:
- `Rpf8Extract` (all four builds) — resolves only top-level hashed entries.
  Plain paths fail in every archive tried: common_0, update_1, update_3,
  update_4, data_0. Hashed lookups using JOAAT of the filename or of the full
  virtual path also fail, so the naming scheme is something else.
- `_downloads/RDR2TextureToolkit/Tools/ArchiveTool` — uncompiled, and pointless
  to compile: it is a WPF GUI, and it opens archives with
  `RageArchiveWrapper7`, i.e. GTA V's RPF **7**. RDR2 uses RPF8. Wrong format.
- `_downloads/RDR2TextureTool-v1.1.3` — texture dictionary (.ytd) editing only.
  It does not open .rpf archives at all.

Therefore anything inside `pack_patch` / `dlcpacks` needs **OpenIV**, installed
under `%LOCALAPPDATA%` in `New Technology Studio\Apps\OpenIV\`, with RDR2 closed.

Vanilla extraction coverage: `_downloads/extract/` holds base-game and
`update_1` common data only. The single genuine vanilla weapon-component file on
disk is the base `weaponcomponents.meta` under
`update_1_common/common/packs/base/data/ai/`. No `pack_patch` or `dlcpacks` tree
has ever been extracted, so the `patch_`, `003_` and `004_` component layers have
no vanilla reference to compare against.

