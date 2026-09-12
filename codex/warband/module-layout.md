# Module source and installed data

Warband loads a selected module from `<Warband>/Modules/<module>/`. `Native` is
the base-game module. A separate mod module does not need to replace Native.

The Module System contains editable Python files such as `module_troops.py`.
Its build exports game data such as `troops.txt` into the directory selected by
`export_dir`. That directory should be the intended mod module. The game reads
the exported files, not the Module System Python source.

Lexeditor edits troop records in Module System source, including well-formed
commented-out records. It exposes names, factions, attributes, flags and equipment;
advanced fields retain source-expression controls. Saves check the source hash,
keep a backup, preserve troop IDs and upgrade code, and validate Python 2 syntax
when the installed validator is available. The existing Save action then builds
the mod. Malformed records stay visible with a source error.

Source: [official Module System documentation, part 1](https://mbmodwiki.github.io/Official_Module_System_Documentation%3A_Part_1).
