# #145: Resolve the remaining missing editor item icons

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/145)

## Requirements and decisions

Complete the editor's item artwork coverage from the existing extracted/imported assets. Do not ask Lexer to repeat the completed OpenIV export. Keep missing artwork distinct from resolver bugs and converter bugs.

## Current implementation and evidence

- Current `master` contains all 347 referenced `ITEM_TEXTURES` PNGs and 235 of the 283 historical `UI_ITEMVIEWER` reference values as local PNGs.
- The old 84-unresolved + 2-converter-failure count is stale. Comparing the historical 283 viewer references against current assets leaves exactly 48 unresolved raw reference values.
- Commit `cf69be7db6bd6122b62a04cd3c0531bb010fb60e` repairs a real resolver defect: whitespace-separated texture IDs are now treated as ordered alternatives instead of being URL-encoded as one impossible filename.
- The 48 residual values are: 7 C5/C6 treasure-map textures; 7 book-reference values; `UI_LETTER_MAYOR_PERM`; `UI_MAP_SERIAL_KILLER`; `UI_NOTE_DINO_01` through `UI_NOTE_DINO_30`; `UI_PHOTO_NORWEGIAN`; and `UI_PHOTO_SC_DAGUERROTYPE`.
- Public/native usage confirms the C5/C6 treasure-map names are real dynamic texture names, so those are not catalog typos.
- The repository already contains `tools/magic-rdr/cli/Rpf6ReadCli.cs` with WTD-to-DDS export support plus `DdsWriter.cs`; remaining converter failures should be diagnosed/repaired there rather than delegated back to a manual extraction session.

## Next agent work

Locate the 48 residual textures in alternate/dynamic dictionaries and identify the exact decoder failures. Add aliases only when source evidence proves identity. Repair the decoder for genuinely present-but-unreadable textures, then regenerate/import the missing PNGs and recompute the residual set before changing issue workflow state.
