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
