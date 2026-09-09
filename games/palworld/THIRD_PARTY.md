# Palworld references

No third-party code is copied or bundled in this initial slice.

## Pocketpair / Palworld Mod Uploader

Primary interoperability reference for the official Palworld v0.7+ mod loader and Steam Workshop package format:

- https://github.com/pocketpairjp/PalworldModUploader
- `docs/en/01-General.md` — official loader introduction and supported package types
- `docs/en/02-Package.md` — `Info.json` package shape and fields
- `docs/en/04-Tech.md` — `PalModSettings.ini`, package-name behavior, InstallRule destinations, DebugMode and Version semantics
- `MainWindow.xaml.cs` — uploader-side validation behavior (alphanumeric PackageName, supported InstallRule types, non-empty Targets)

Lexeditor's Python implementation is independent and uses these files as behavioral/documentation references only. No Palworld game data, Pocketpair assets, Steam credentials, or uploader source files are redistributed.
