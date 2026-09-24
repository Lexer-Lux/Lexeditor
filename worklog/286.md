# #286: Online consumable wheel mappings

[Live issue](https://github.com/Lexer-Lux/Lexeditor/issues/286)

## Current requirement

Deliver Irish Whiskey and Old Tom Gin wheel mappings while preserving existing custom items and effects. Catalog entries alone do not prove full Online-content support.

## Delivery audit: 2026-09-08

Both the source MyOverhaul and installed game lml/MyOverhaul already contain exactly one mapping for each target: CONSUMABLE_OLDTOM_GIN to PLAYER_PROVISIONS at order 235; CONSUMABLE_IRISH_WHISKEY to PLAYER_PROVISIONS at order 275. Both install.xml files register update:/x64/packs/base/data/ai/quickselectitems.ymt to quickselectitems.ymt. Both catalogs contain exactly one target record in group CONSUMABLE, category CI_CATEGORY_COLLECTIBLE.

The source and installed quickselectitems.ymt files are byte-identical. SHA-256: 437e19a8e3c03c4d9e977c507a8807fa687bfaae33cbfafede60084096ef4a32.

No merge or file write was required. No source or installed game data was changed. The legacy #195 verifier rejects the current unrelated-entry count (1867 versus its historical 1865), after passing reference, catalog and installation checks. Do not remove unrelated entries to satisfy that old baseline.

## Acceptance boundary

The two mappings are installed; this audit does not prove wheel visibility in game. Test each owned bottle in Story Mode: open the item wheel, locate it under provisions, use it, and report a missing name, icon, slot or effect. No game was launched for this audit. Full imported Online-content support remains broader than these two mappings.

## 2026-09-22 misc-fixes disposition
Mappings prepared and audited in source; install plus game proof pending. Test, needs the game: own each bottle in Story Mode, open the item wheel, locate it under provisions, use it, and report any missing name, icon, slot, or effect. Do not touch unrelated catalog entries to satisfy the old 1865 baseline. Issue stays actionable.

## 2026-09-23 master: flipped to waiting with concrete checklist

Posted the exact game-session checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
