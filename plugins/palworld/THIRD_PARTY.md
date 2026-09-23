# Palworld references

No third-party code or proprietary Palworld data is bundled.

## Pocketpair / Palworld Mod Uploader

Primary interoperability reference for the official Palworld v0.7+ mod loader and Steam Workshop package format:

- https://github.com/pocketpairjp/PalworldModUploader
- `docs/en/01-General.md` — official loader introduction and supported package types
- `docs/en/02-Package.md` — `Info.json` package shape and fields
- `docs/en/04-Tech.md` — `PalModSettings.ini`, package-name behavior, InstallRule destinations, DebugMode and Version semantics
- `MainWindow.xaml.cs` — uploader validation and the default `./PalSchema/` target

Lexeditor's package implementation is independent and uses these files as behavioral/documentation references.

## Okaetsu / PalSchema

Primary reference for PalSchema raw DataTable patch semantics:

- https://github.com/Okaetsu/PalSchema
- License: MIT
- `website/docs/gettingstarted.md` — mod tree, raw patch shape, `.json`/`.jsonc`, targeted-field conflict behavior
- `src/Loader/PalRawTableLoader.cpp` — table/row/property application, `Rows` rejection, wildcard/filter handling, row add/delete, existing-property edits
- `src/Utility/JsonHelpers.cpp` — direct non-recursive raw-folder iteration and JSONC comment parsing
- `src/Loader/WildcardFilter/*` — `$Filters` runtime behavior

Lexeditor does not copy PalSchema code. Its Python parser/writer is an independent implementation of the documented/runtime-observed format boundary. The upstream MIT license informs compatibility/provenance but no PalSchema binary, UE4SS binary, schema dump, or game data is redistributed.
