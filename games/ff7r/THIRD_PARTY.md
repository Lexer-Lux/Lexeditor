# Third-party references and tools

## FF7 Remake Data Editor

The narrow `DataObject` package reader/writer in this plugin is a clean Python
implementation based on the documented behavior and MIT-licensed source of
Jordan Tucker's **FF7 Remake Data Editor**:

- https://github.com/jordanbtucker/ff7r-data-editor
- License: MIT

That project established the FF7R DataObject `.uasset` name/export-table shape,
the `.uexp` property type codes and fixed-row layout, and the safe same-size
editing model used here. Lexeditor does not bundle its application or proprietary
game data.

## FF7R Text Tool

The `GameContents/Text/<language>/*_TxtRes` reader/writer is a clean Python
implementation based on the documented behavior and MIT-licensed source of
MatyaModding's **ff7r-text-tool**:

- https://github.com/matyamod/ff7r-text-tool
- License: MIT

That project documents the FF7R text-resource entry/sub-entry layout, Unreal
FString encoding, name-map references and the paired `.uasset` serialized-size
field required when variable-length text changes. Lexeditor does not bundle the
tool or any extracted game text.

## repak

Lexeditor downloads a pinned release of **repak** only when the user chooses to
install the FF7R archive helper:

- https://github.com/trumank/repak
- License: dual Apache-2.0 / MIT
- Pinned release: v0.2.3

repak reads the installed Unreal Engine PAK indexes/files on demand and packs the
separate Lexeditor project tree into a mod PAK. FF7R's `../../../` mount point is
passed explicitly when listing, extracting and packing. repak is not committed
into this repository.

## Improved Keyboard and Mouse Controls / Native Mod Loader research

The FF7R native-runtime probe uses independently implemented compatibility checks
informed by TheUnlocked's maintained, MIT-licensed **ff7r-kbm-hook**:

- https://github.com/TheUnlocked/ff7r-kbm-hook
- License: MIT

That project provides public evidence for the Native Mod Loader `Init()` export
contract and current FF7R byte signatures around map control and raw-input
initialization. Lexeditor uses those signatures only as compatibility probes. It
does not copy the hook implementation and does not treat those known addresses as
the cutscene-speed or minimap-toggle hook sites required by #413/#414.
