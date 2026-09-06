# GitHub #153 - Restore every custom map icon

## fuckups.txt recurrence audit

- The project had already proven that the standalone streamed `lex_blips`
  dictionary renders custom map linkages as black quads. Adding later textures
  nevertheless kept rebuilding and reinstalling that rejected dictionary.
- Archive existence, a streamed-texture request, and linkage presence are not
  visual acceptance. The safe path is the complete 432-texture Rockstar
  `INVENTORY_ITEMS_MP` dictionary plus every custom texture, with every custom
  linkage pointing to that resident dictionary.
- A partial resident replacement is forbidden. The builder must start from all
  432 Rockstar textures and append the complete custom set; the verifier must
  fail if one older icon disappears when a new one is added.

## Current repair

All thirteen custom map textures are inputs to the existing complete
`INVENTORY_ITEMS_MP` builder. Every custom `LEX_BLIP_*` linkage except the
unchanged vanilla newspaper linkage uses `INVENTORY_ITEMS_MP`. Runtime modules
request that resident dictionary only. The rejected `lex_blips.ytd` is removed
from the build/install/live paths rather than left available for the next
feature to reuse accidentally.

Runtime acceptance after a full restart remains mandatory: every old and new
custom marker must show its actual transparent artwork, and ordinary Rockstar
icons must remain intact.

## Rejected dictionary physically removed

After Lexer correctly questioned why a known-broken dictionary was retained,
all remaining standalone `lex_blips.ytd` archives were removed from the source
tree, disabled/quarantine directory, build output, and game-root mod storage.
The two obsolete scripts capable of rebuilding that archive and their private
YTD builder binaries were also removed. The thirteen DDS icon inputs were
renamed/moved to `build_resident_map_icons/dds`; they are source inputs for the
working complete `INVENTORY_ITEMS_MP` replacement, not a standalone resource.
The preparation script is now `prepare_resident_map_icons.py`, all verifier and
resident-builder references use that name/path, and #153's verifier rejects any
reappearance of the deleted archives or standalone builders.
