# Chrono Trigger Steam — fresh replacement

This plugin deliberately replaces the rejected #454 architecture. The old code is historical evidence only; it is not the implementation base.

## Supported boundary

The replacement targets the Steam release (App ID `613830`). Installed `resources.bin` is always read-only; edits go to an external project and export as replacement-only `.ctp` packages.

Current structured editors cover:

- keyed `Localize/<lang>/msg/*.txt` text;
- `Mapinfo` area settings, scene map layer tiles, RLE property runs and current-PC render settings;
- area exits and treasure;
- field/world RGB555 palettes and world palette-animation colors;
- field graphics-set references, tile assemblies and fixed-count chip animations;
- current-PC sprite descriptors and fixed sprite assemblies;
- the seven active fixed 23-byte world headers;
- fixed world map layers, tile-property nibbles, music-transition nibbles, exits and triggers.

Unknown bits, sentinels, unmodelled words, counts, compressed run boundaries and trailing bytes are preserved unless a documented field is explicitly edited. No generic raw-file editor is counted as format integration.

## CTP and Mod Library

`.ctp` is a standard ZIP whose members use `resources.bin` paths. Export rejects added paths that are not present in the source archive because known CTP loaders cannot apply them.

The shared Mod Library can inspect/import direct CTPs or expanded Game/Localize trees and make an imported CTP into an editable project copy. An author-test adapter also implements the CTExt layout proved by public source: selected CTPs are staged under `mods/LexeditorLibrary/` and represented in `ctext.json`'s `mods.load_order`.

CTExt itself is **not bundled or installed**: its audited repository has no clear top-level redistribution license. The adapter therefore remains unverified and `mods_load=False` until an installed Steam game proves activation and removal in-game.

For selected Lexeditor CTPs, load order is low to high and a later package wins a whole-resource collision. Lexeditor reports those collisions, preserves external CTExt load-order entries, and refuses to replace or remove a managed deployment changed outside Lexeditor.

## Remaining boundaries

Not integrated or not claimed complete:

- variable Atel field-event/cutscene script bodies;
- variable world script bodies;
- raw/raster field/world graphics editing;
- remaining character animation/graphics families beyond the proven descriptor/assembly slices;
- gameplay DataTable families without independently verified typed schemas.

Real installed-game CTP loading and native behavior remain separate acceptance requirements.

## Safety

- Installed `resources.bin` is immutable.
- Project writes are stale-hash guarded and atomic.
- CTP export is deterministic and contains only modified existing archive resources.
- CTExt author-test deployment is namespaced, stale-guarded and reversible; external load-order entries are retained.
- No proprietary game dump or CTExt binary is committed or bundled.
