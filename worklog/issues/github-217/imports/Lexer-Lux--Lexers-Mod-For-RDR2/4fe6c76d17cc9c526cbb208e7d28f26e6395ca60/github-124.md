# GitHub #124 - duplicate Misc settings categories

## Player-visible failure

LEXEDITOR displayed two indistinguishable `Misc` categories. Its curated
`MISC` feature card claimed `Misc/TaggedOnlyOnMinimap`, while unclaimed keys
from the same INI section were rendered afterward as a second raw `Misc` card.
The settings API also represented repeated, case-variant INI section blocks as
separate sections even though Win32 INI lookup treats their names as the same.

## Implementation

The settings API now merges repeated section names and keys case-insensitively,
matching Win32 INI semantics without rewriting or reordering the source INI.
LEXEDITOR now queues settings cards by their case-insensitive displayed title,
so curated `MISC` entries and the remaining raw `Misc` entries share one card.

## Acceptance

`verify_settings_misc_issue_124.py` exercises repeated `[Misc]`/`[MISC]`
blocks and checks the curated/raw card merge. Open LEXEDITOR Settings and
confirm there is exactly one Misc card containing Tagged Only On Minimap,
Auto-Bank, and Pause Map Zoom Multiplier.
