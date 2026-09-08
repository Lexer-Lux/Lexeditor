# Third-party references and tools

## FF7 Remake Data Editor

The narrow `DataObject` package reader/writer in this plugin is a clean Python
implementation based on the documented behavior and MIT-licensed source of
Jordan Tucker's **FF7 Remake Data Editor**:

- https://github.com/jordanbtucker/ff7r-data-editor
- License: MIT

That project established the FF7R DataObject `.uasset` name/export-table shape,
the `.uexp` property type codes and fixed-row layout, and the safe same-size
editing rule used here. Lexeditor does not bundle its application or proprietary
game data.

## repak

Lexeditor downloads a pinned release of **repak** only when the user chooses to
install the FF7R archive helper:

- https://github.com/trumank/repak
- License: dual Apache-2.0 / MIT
- Pinned release: v0.2.3

repak reads the installed Unreal Engine PAK indexes/files on demand and packs the
separate Lexeditor project tree into a mod PAK. It is not committed into this
repository.
