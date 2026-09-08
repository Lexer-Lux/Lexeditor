# #145: Resolve the remaining missing editor item icons

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/145)

## Requirements and decisions

Complete the editor's item artwork coverage from the existing extracted/imported assets. Do not ask Lexer to repeat the completed OpenIV export. Keep missing artwork distinct from resolver bugs and converter bugs.

## Current implementation and evidence

- Current `master` contains all 347 referenced `ITEM_TEXTURES` PNGs and 235 of the 283 historical `UI_ITEMVIEWER` reference values as local PNGs.
- Commit `cf69be7db6bd6122b62a04cd3c0531bb010fb60e` repairs a real resolver defect: whitespace-separated texture IDs are treated as ordered alternatives instead of being URL-encoded as one impossible filename.
- PR #418 / squash commit `ea183fd2abcbc9698653925202a34fb7ce3282ad` resolves all 7 C5/C6 treasure-map references on demand from the installed `x64/dlcpacks/dlc_content_extra/dlc.rpf` → `x64/textures/ui/ui_itemviewer.ytd`. Generated PNGs stay under Lexeditor's private cache; no new Rockstar textures are committed.
- `RpfCli` returns decoded resources with an internal uncompressed RSC8 header. The #418 fallback losslessly rewraps that decoded virtual+physical payload as standard raw-deflate RSC8 before `texfury` decodes the YTD.
- Both RDR2 checks and the cross-plugin Warband checks passed for #418.
- The residual set is now exactly **41 raw viewer references**: 7 book-reference values; `UI_LETTER_MAYOR_PERM`; `UI_MAP_SERIAL_KILLER`; `UI_NOTE_DINO_01` through `UI_NOTE_DINO_30`; `UI_PHOTO_NORWEGIAN`; and `UI_PHOTO_SC_DAGUERROTYPE`.
- OpenIV's current RDR2 archive-name database exposes only three `ui_itemviewer` layers: base `textures_1.rpf`, patch `update_4.rpf`, and `dlc_content_extra`. The 41 residual names are absent from all three named texture lists. Their JOAATs are also absent from the base dictionary's unresolved `.hashes` list. Therefore these 41 are not ordinary missing static `UI_ITEMVIEWER` texture entries and should not be sent through another blind extraction pass.
- `collectibles_ymt.xml` independently proves `UI_NOTE_DINO_01` through `UI_NOTE_DINO_30` are real game-data references paired with the 30 dinosaur-bone document records, despite having no static texture entries. This strongly points to document/item-viewer dynamic rendering rather than spelling errors.

## Next agent work

Trace the 41 residual references through the document/item-viewer data and scripts. Identify the dynamic source or proven static alias for each family. Add aliases only when source evidence proves identity. If the game renders a reference dynamically, implement an editor-side exact preview from the same underlying data instead of manufacturing a guessed icon. Recompute the residual set before changing issue workflow state.
