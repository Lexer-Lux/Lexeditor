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

## FF7R Font Mod Tools

The local-only menu-font theming path is a narrow Python implementation based on
the documented layouts and MIT-licensed source of MatyaModding's
**FF7R-font-mod-tools**:

- https://github.com/matyamod/FF7R-font-mod-tools
- License: MIT

That project documents the `GameContents/Menu/Resident/Font/JP/SystemFont*4K`
glyph UEXP record shape and the matching
`GameContents/Menu/Billboard/Common/U_Com_JP_SystemFont*4K-01` 2048x2048 BC5
bitmap-atlas layout. Lexeditor validates those exact installed assets, decodes
`SystemFontNormal` only into the user's private cache, and uses the resulting
atlas/glyph metrics for editor chrome. It does not bundle or publish Square Enix
font assets.

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

## FinalFantasy7Remake-Menu interoperability research

The guarded HP runtime implementation is informed by public interoperability
information in xCENTx's **FinalFantasy7Remake-Menu** repository:

- https://github.com/xCENTx/FinalFantasy7Remake-Menu
- No repository license file was present when this reference was recorded.

Lexeditor does not copy or bundle that project's implementation. It uses factual
process-layout information (the `AGameState` / `APlayerStats` field layout and a
RIP-relative game-state lookup instruction shape) as a research reference, then
independently validates the installed executable at runtime. No fixed RVA from
that project is shipped or trusted.

## EndGameProj generated Remake API research

Public generated Remake headers in narknon's **EndGameProj** are used only as
interoperability/research evidence for reflected type, property, enum and function
names such as `EGameSpeed_CUT`, `AEndGameState::SetGameSpeed`, ATB DataObject
fields, and menu widget settings:

- https://github.com/narknon/EndGameProj

These generated declarations are not bundled into Lexeditor and are not treated
as current installed-build offsets or validated hook addresses. Installed-game
probes must still establish the concrete target before a runtime mutation can be
enabled.
