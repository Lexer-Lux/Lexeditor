# FINAL FANTASY VII REMAKE INTERGRADE

## PC product layout

Lexeditor identifies the PC product by:

- Steam app ID `1462040`.
- Executable `End/Binaries/Win64/ff7remake_.exe`.
- Unreal archives under `End/Content/Paks`.
- Deployable mod PAKs under `End/Content/Paks/~mods`.

Steam commonly names the install directory `FINAL FANTASY VII REMAKE`; Epic
commonly uses `FFVIIRemakeIntergrade`. The shared installation manager also uses
Steam manifests, uninstall data, Epic manifests, manual location and persisted
selection, so these defaults are fallbacks rather than hard-coded requirements.

## DataObject editing contract

The first integrated game-data surface is
`End/Content/GameContents/DataObject/**.{uasset,uexp}`.

The `.uasset` supplies the Unreal name table and export metadata. The paired
`.uexp` begins with a table header, property definitions and fixed-layout rows.
Supported property types are boolean, byte, signed 16-bit integer, signed 32-bit
integer, float, FString and FName, including fixed-length arrays. FString values
are readable but not editable because changing their byte length would move all
following data. FName edits are limited to names already present in the
`.uasset`. Numeric/FName writes patch only their proved byte ranges.

Unknown bytes and the original `.uasset` are preserved. Saving writes only under
the selected Lexeditor project `content/` tree. It never modifies an installed
base PAK.

## Archive workflow

Pinned `repak` v0.2.3 is a Lexeditor helper, not a bundled binary. Lexeditor
indexes installed PAKs and caches only the DataObject path catalog. A selected
DataObject pair is extracted on demand with `repak get`, avoiding a bulk game
unpack. The catalog signature includes PAK path, size and modification time so a
game update invalidates stale extracted-source cache entries.

Build packs only `<project>/content` into `<project>/build/Lexeditor-FF7R_P.pak`.
Deploy is a separate explicit action that copies that built PAK to the game's
`~mods` directory.

## Proven limits

- This is not a generic Unreal asset editor. Only the FF7R DataObject table shape
  is integrated.
- String resizing, adding/removing properties, adding/removing rows, changing
  array lengths and adding new FNames require package rebuilding and are not yet
  supported.
- Source/API/synthetic-fixture checks do not establish live in-game acceptance.

## Installed-PAK extraction defect and its fix (2026-09-09)

The plugin cannot read any asset from a real FF7R install. `build_index`
succeeds and lists 1128 DataObjects, but extracting even the first one fails,
so opening any asset in the editor fails. This is not specific to UMG or to the
battle HUD; it affects the shipping DataObject surface equally. The existing
checks did not catch it because they run on synthetic fixtures and never open an
installed PAK, which this file already warns about under proven limits.

Pinned `repak` v0.2.3 panics in `repak/src/entry.rs:397`:

```
index out of bounds: the len is 3 but the index is 3
```

Cause. FF7R ships PAK version 4, which predates the FName-based compression
table, so `pak.rs` hardcodes exactly three legacy slots: Zlib, Gzip, Oodle at
indices 0, 1 and 2. Both entry readers convert the stored value with `n - 1`, so
a stored 4 becomes slot 3 and indexes past that three-element table. Legacy
Unreal stored this field as a bitflag, where 1 is Zlib, 2 is Gzip and 4 is
Custom, which FF7R uses for Oodle. repak treats the value as a dense slot index
instead, so any Custom/Oodle entry panics.

Only entries small enough to be stored uncompressed extract today. A sample of
36 entries across six PAKs returned 4 successes, all between 118 and 181 bytes.

Not the cause, both ruled out by testing. v0.2.3 is the latest release, so there
is no newer build to move to, and master carries the identical line. The CLI
already enables the `oodle` feature by default; supplying the Oodle library that
`oodle_loader` expects, `oo2core_9_win64.dll` matching its pinned SHA-256
`6f5d41a7...f457`, next to `repak.exe` does not help, because the failure is the
slot lookup rather than a missing decompressor. That library is now present in
the helper directory and is still required once the lookup is fixed.

Fixing this needs the legacy slot mapping corrected so Custom resolves to Oodle,
which means building repak from source, or reading PAK entries directly with
Oodle called through the shipped library. The game's own
`Engine/Binaries/ThirdParty/Oodle/Win64/oo2core_7_win64.dll` is also present.

Battle HUD assets, located for issue research but not yet readable:
`Menu/Resident/Battle/Status` is the party member panel, alongside `ATBGauge`,
`Gauge_Cell`, `Status_BtnGuide`, `Status_LimitEffect_00`/`_01`, `EnemyStatus`,
and the textures `U_CharaStatus_Base_02` and `U_CharaStatus_ATB_03`.

### Fixed by reading PAK entries directly

`games/ff7r/pak_reader.py` now parses the version 4 index and entry payloads
itself, so the plugin no longer depends on the repak defect being fixed
upstream. repak remains responsible for listing, packing and archive info,
which it performs correctly, and stays the fallback if the reader rejects an
archive shape.

Parsing the index confirmed the cause directly rather than inferring it from the
panic: of 72,214 entries in `pakchunk0_s22`, 65,909 store compression 4 and
6,305 store 0, matching the share that extracted before. Value 4 is the legacy
Custom bitflag, not a slot index.

Oodle payloads decode through the library the game already ships; no decoder is
bundled. `Menu/Resident/Battle/Status.uasset` now decodes to its full 349,289
bytes with valid cooked-package magic, and `DataObject/Resident/BattleStatusChange`
parses to its five real properties.

`cryptography` is now a runtime requirement, for the encrypted index.

